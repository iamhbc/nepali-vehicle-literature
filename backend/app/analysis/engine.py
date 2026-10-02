"""AnalysisEngine — orchestrates the pipeline.

    input → language detection → normalization → corpus retrieval → lexical &
    concept cues → [LLM structured analysis | baseline] → evidence verification
    → related expressions → references → cultural map → persisted result

``stream()`` yields progress events (and, in LLM mode, an instant baseline
"preliminary" reading) so the UI never waits on a blank screen.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..knowledge import get_knowledge
from ..models import Analysis, Phrase
from ..nlp.language import detect_language
from ..nlp.normalize import match_key, normalize_text
from ..nlp.transliterate import transliterate
from ..retrieval.search import CorpusIndex, get_corpus_index
from . import baseline, prompts
from .graph import build_graph
from .llm import AnthropicProvider, LLMError, LLMProvider, parse_model
from .schema import (
    AnalysisPayload,
    AnalysisResult,
    ConceptNote,
    CorpusMatch,
    EngineInfo,
    LexicalSignal,
    ReferenceOut,
    RelatedEntry,
    strict_json_schema,
)
from .verify import verify

log = logging.getLogger(__name__)

STAGES = {
    "normalize": "Reading the inscription",
    "retrieve": "Searching the research corpus",
    "cues": "Noting cultural and lexical cues",
    "interpret": "Interpreting meaning and context",
    "verify": "Checking every quote against the phrase",
    "map": "Drawing the cultural map",
}


class AnalysisInputError(ValueError):
    pass


def _event(name: str, data) -> dict:
    return {"event": name, "data": data}


class AnalysisEngine:
    def __init__(self, settings: Settings, corpus: CorpusIndex, llm: LLMProvider | None) -> None:
        self.settings = settings
        self.corpus = corpus
        self.llm = llm
        self._schema = strict_json_schema(AnalysisPayload)

    @property
    def mode(self) -> str:
        return "llm" if self.llm else "baseline"

    # --- Public API ------------------------------------------------------------

    async def analyze(self, db: Session, text: str, context: dict | None = None, use_cache: bool = True) -> AnalysisResult:
        result = None
        async for ev in self.stream(db, text, context, use_cache):
            if ev["event"] == "result":
                result = ev["data"]
        assert result is not None
        return AnalysisResult.model_validate(result)

    async def stream(self, db: Session, text: str, context: dict | None = None, use_cache: bool = True) -> AsyncIterator[dict]:
        started = time.perf_counter()
        kb = get_knowledge()
        normalized = normalize_text(text)
        self.validate(normalized)
        language = detect_language(normalized)
        yield _event("stage", {"stage": "normalize", "message": STAGES["normalize"], "language": language.as_dict()})

        mode = self.mode
        model = self.llm.model if self.llm else None
        cache_key = self._cache_key(normalized, mode, model, context)
        if use_cache:
            cached = db.scalar(select(Analysis).where(Analysis.cache_key == cache_key).order_by(Analysis.created_at.desc()))
            if cached:
                data = dict(cached.result)
                data["engine"] = {**data["engine"], "cached": True}
                yield _event("result", data)
                return

        # Retrieval
        match = self.corpus.find_match(normalized)
        match_phrase = db.get(Phrase, match[0].id) if match else None
        neighbours_hits = self.corpus.related(normalized, k=self.settings.llm_retrieval_k,
                                              exclude={match[0].id} if match else None, min_score=0.05)
        neighbours = []
        for h in neighbours_hits:
            p = db.get(Phrase, h.id)
            neighbours.append((h.meta, p.coding if p else {}, h.score))
        yield _event("stage", {"stage": "retrieve", "message": STAGES["retrieve"],
                               "corpus_match": match[0].corpus_id if match else None,
                               "neighbours": [m.corpus_id for m, _, _ in neighbours]})

        # Cues
        hits = kb.match_lexicon(normalized)
        concept_terms = baseline.concept_key_terms(normalized, kb)
        yield _event("stage", {"stage": "cues", "message": STAGES["cues"],
                               "cues": sorted({h.token for h in hits}), "concepts": [t.term for t in concept_terms]})

        warnings: list[str] = []
        if language.language not in ("ne", "mixed"):
            warnings.append(language.note or "The input does not look like Nepali in Devanagari.")

        def baseline_payload() -> AnalysisPayload:
            if match and match_phrase:
                p = baseline.from_corpus(normalized, match[0], match_phrase.coding or {}, kb)
                p.transliteration = match_phrase.transliteration or transliterate(normalized)
                p.key_terms = concept_terms
                return p
            return baseline.from_signals(normalized, hits, neighbours, concept_terms, kb)

        engine_notes: list[str] = []
        usage = None
        if mode == "llm":
            prelim = self._assemble(db, normalized, text, language.as_dict(), baseline_payload(), "baseline", None,
                                    match, match_phrase, hits, concept_terms, [], started, persist=False,
                                    notes=["Preliminary reading while the full analysis runs."], cache_key=cache_key)
            yield _event("preliminary", prelim.model_dump(mode="json"))
            yield _event("stage", {"stage": "interpret", "message": STAGES["interpret"]})
            exemplars = []
            if match and match_phrase:
                exemplars.append((match[0], match_phrase.coding or {}))
            exemplars += [(m, c) for m, c, s in neighbours if s >= 0.1][: self.settings.llm_retrieval_k]
            try:
                response = await self.llm.structured(
                    prompts.system_prompt(),
                    prompts.user_content(normalized, exemplars, context),
                    self._schema,
                    self.settings.llm_max_tokens,
                )
                payload = parse_model(AnalysisPayload, response.data)
                model, usage = response.model, response.usage
                if not payload.transliteration.strip():
                    payload.transliteration = transliterate(normalized)
            except LLMError as exc:
                log.warning("LLM analysis failed, using baseline: %s", exc)
                warnings.append(f"The AI interpretation engine was unavailable ({exc}). Showing the baseline reading instead.")
                payload, mode, model = baseline_payload(), "baseline", None
        else:
            payload = baseline_payload()
            engine_notes.append(
                "Baseline engine: research-corpus coding, lexicon cues and rule-based rhetoric. "
                "Configure an LLM provider for full interpretive analysis."
            )
            if not match:
                warnings.append("This phrase is not in the research corpus, so the reading is limited to surface cues and similar entries.")

        yield _event("stage", {"stage": "verify", "message": STAGES["verify"]})
        payload, verification, v_warnings = verify(payload, normalized)
        warnings += v_warnings
        yield _event("stage", {"stage": "map", "message": STAGES["map"]})

        if usage:
            engine_notes.append(f"Tokens: {usage.get('input_tokens')} in / {usage.get('output_tokens')} out.")
        result = self._assemble(db, normalized, text, language.as_dict(), payload, mode, model, match, match_phrase,
                                hits, concept_terms, warnings, started, persist=True, notes=engine_notes,
                                verification=verification, cache_key=cache_key)
        yield _event("result", result.model_dump(mode="json"))

    # --- Helpers ---------------------------------------------------------------

    def validate(self, text: str) -> None:
        if not text:
            raise AnalysisInputError("Please enter a phrase to analyse.")
        if len(text) > self.settings.max_phrase_chars:
            raise AnalysisInputError(f"Please keep the phrase under {self.settings.max_phrase_chars} characters.")
        if not any(ch.isalpha() for ch in text):  # Devanagari letters are alphabetic; digits are not
            raise AnalysisInputError("The input has no letters to analyse.")

    def _cache_key(self, text: str, mode: str, model: str | None, context: dict | None) -> str:
        kb = get_knowledge()
        raw = json.dumps([prompts.PROMPT_VERSION, mode, model, self.settings.llm_effort, kb.version,
                          self.corpus.revision, match_key(text), text, context or {}], ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _assemble(self, db, normalized, original, language, payload, mode, model, match, match_phrase, hits,
                  concept_terms, warnings, started, persist, notes, cache_key, verification=None) -> AnalysisResult:
        kb = get_knowledge()
        if verification is None:
            payload, verification, _ = verify(payload, normalized)

        codes = [t.code for t in payload.themes]
        exclude = {match[0].id} if match else set()
        related = [
            RelatedEntry(id=h.id, corpus_id=h.meta.corpus_id, text=h.meta.text, translation=h.meta.translation,
                         score=h.score, reasons=h.reasons, codes=h.meta.codes, needs_review=h.meta.needs_review,
                         status=h.meta.status)
            for h in self.corpus.related(normalized, k=6, codes=codes, exclude=exclude)
        ]

        concepts = []
        for hit in kb.match_concepts(normalized):
            c = kb.concepts_by_slug[hit.slug]
            concepts.append(ConceptNote(slug=c["slug"], term=c["term"], translit=c["translit"], gloss=c["gloss"],
                                        explanation=c["explanation"], surface=hit.token, references=c.get("references", [])))

        labels = {f.label.lower() for _, fs in _all_findings(payload) for f in fs}
        labels |= {t.code.lower() for t in payload.themes}
        labels |= {f.love_type for f in payload.love.findings} | {f.family for f in payload.emotion.findings}
        signals = []
        for h in hits:
            reflected = any(sig.split(":", 1)[1].lower() in labels for sig in h.signals)
            signals.append(LexicalSignal(token=h.token, gloss=h.gloss, signals=h.signals, weak=h.weak, reflected_in_reading=reflected))

        topics = set(codes) | {f.label for _, fs in _all_findings(payload) for f in fs}
        topics |= {f.love_type for f in payload.love.findings} | {c.slug for c in concepts}
        if payload.emotion.findings:
            topics.add("emotion")
        if payload.love.findings:
            topics.add("love")
        if payload.gender_power.power_stance not in ("not_applicable", "ambiguous"):
            topics.add(payload.gender_power.power_stance)
        if payload.implied.implied:
            topics.add("implied")
        if concepts:
            topics.add("cultural_concept")
        refs = sorted(kb.references_for(topics), key=lambda r: -len(r["matched_topics"]))[:6]
        references = [ReferenceOut(**{k: r.get(k) for k in ReferenceOut.model_fields}) for r in refs]

        corpus_match = None
        if match and match_phrase:
            corpus_match = CorpusMatch(
                id=match_phrase.id, corpus_id=match_phrase.corpus_id, similarity=match[1], exact=match[1] >= 0.999,
                text=match_phrase.searchable_text, translation=match_phrase.translation, codes=match[0].codes,
                coding=match_phrase.coding or {}, needs_review=match_phrase.needs_review, review_reason=match_phrase.review_reason,
            )

        duration_ms = int((time.perf_counter() - started) * 1000)
        info = EngineInfo(mode=mode, model=model, effort=self.settings.llm_effort if mode == "llm" else None,
                          taxonomy_version=kb.version, prompt_version=prompts.PROMPT_VERSION,
                          duration_ms=duration_ms, cached=False, notes=notes)
        graph = build_graph(normalized, payload, related, [c.model_dump() for c in concepts])
        result = AnalysisResult(
            id="preliminary", created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            input_text=original, normalized_text=normalized, language=language, engine=info, payload=payload,
            corpus_match=corpus_match, related=related, concepts=concepts, lexical_signals=signals,
            references=references, verification=verification, graph=graph, warnings=warnings,
        )
        if persist:
            row = Analysis(cache_key=cache_key, input_text=original, match_key=match_key(normalized), engine=mode,
                           model=model, taxonomy_version=kb.version, result={}, duration_ms=duration_ms,
                           phrase_id=match_phrase.id if match_phrase else None)
            db.add(row)
            db.flush()
            result.id = row.id
            row.result = result.model_dump(mode="json")
            db.commit()
        return result


def _all_findings(p: AnalysisPayload):
    return [
        ("emotion", p.emotion.findings), ("love", p.love.findings), ("relationship", p.relationships.findings),
        ("social", p.social.findings), ("economic", p.economic.findings), ("political", p.political.findings),
        ("gender_power", p.gender_power.findings), ("cultural", p.cultural.findings),
        ("philosophical", p.philosophical.findings), ("rhetoric", p.rhetoric.findings),
    ]


_engine: AnalysisEngine | None = None


def get_engine() -> AnalysisEngine:
    global _engine
    if _engine is None:
        s = get_settings()
        llm = AnthropicProvider(s) if s.llm_enabled else None
        _engine = AnalysisEngine(s, get_corpus_index(), llm)
    return _engine
