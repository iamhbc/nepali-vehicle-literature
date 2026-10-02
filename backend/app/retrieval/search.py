"""Corpus retrieval: semantic search, related expressions, and near-duplicate detection.

Two vector namespaces are kept per phrase:

* ``text``  — the Nepali wording only (for phrase-to-phrase similarity)
* ``full``  — wording + translation + researcher interpretation + theme labels
  (for free-text research queries in English or Nepali)

Scores are blended with theme overlap so results stay anchored to the
researcher codebook, and every hit carries a plain-language reason.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass, field

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import engine as db_engine
from ..knowledge import get_knowledge
from ..models import Phrase, PhraseEmbedding
from ..nlp.normalize import match_key, tokenize
from .embeddings import Embedder, english_terms, make_embedder
from .index import MemoryVectorIndex, PgVectorIndex, VectorIndex

log = logging.getLogger(__name__)


@dataclass
class DocMeta:
    id: int
    corpus_id: str
    text: str
    translation: str | None
    codes: list[str]
    valence: str | None
    status: str
    needs_review: bool
    key: str
    tokens: set[str] = field(default_factory=set)
    en_terms: set[str] = field(default_factory=set)


@dataclass
class Hit:
    id: int
    score: float
    vector_score: float
    theme_score: float
    reasons: list[str]
    meta: DocMeta


def _full_document(p: Phrase) -> str:
    kb = get_knowledge()
    coding = p.coding or {}
    theme_bits = []
    for code in (t.theme_code for t in p.themes if t.status != "rejected"):
        th = kb.themes.get(code)
        if th:
            theme_bits.append(f"{th['label_en']}. {th['definition']}.")
    parts = [
        p.searchable_text,
        p.translation or "",
        coding.get("deeper_meaning") or "",
        " ".join(p.original_theme or []),
        " ".join(coding.get("emotions") or []),
        " ".join(theme_bits),
    ]
    return "\n".join(x for x in parts if x)


class CorpusIndex:
    def __init__(self, embedder: Embedder, index: VectorIndex) -> None:
        self.embedder = embedder
        self.index = index
        self.meta: dict[int, DocMeta] = {}
        self.revision = "0"
        self._lock = threading.Lock()

    def _update_revision(self, db: Session) -> None:
        """Changes whenever corpus entries change; part of the analysis cache key."""
        count, latest = db.execute(select(func.count(Phrase.id), func.max(Phrase.updated_at))).one()
        self.revision = f"{count}:{latest.isoformat() if latest else ''}"

    # --- Building --------------------------------------------------------------

    def build(self, db: Session) -> None:
        phrases = db.scalars(select(Phrase).where(Phrase.status != "archived")).all()
        with self._lock:
            self.meta = {}
            if isinstance(self.index, MemoryVectorIndex):
                self.index = MemoryVectorIndex()
            self._add(db, phrases)
            self._update_revision(db)
        log.info("Corpus index built: %d phrases (%s)", len(phrases), self.embedder.name)

    def refresh(self, db: Session, phrase_ids: list[int]) -> None:
        phrases = db.scalars(select(Phrase).where(Phrase.id.in_(phrase_ids))).all()
        with self._lock:
            live = [p for p in phrases if p.status != "archived"]
            gone = [pid for pid in phrase_ids if pid not in {p.id for p in live}]
            for pid in gone:
                self.meta.pop(pid, None)
            if gone and isinstance(self.index, MemoryVectorIndex):
                self.index.remove("text", gone)
                self.index.remove("full", gone)
            self._add(db, live)
            self._update_revision(db)

    def _add(self, db: Session, phrases: list[Phrase]) -> None:
        if not phrases:
            return
        text_docs = [p.searchable_text for p in phrases]
        full_docs = [_full_document(p) for p in phrases]
        text_vecs = self._cached_vectors(db, phrases, text_docs, "text")
        full_vecs = self._cached_vectors(db, phrases, full_docs, "full")
        ids = [p.id for p in phrases]
        self.index.upsert("text", ids, text_vecs)
        self.index.upsert("full", ids, full_vecs)
        for p in phrases:
            text = p.searchable_text
            self.meta[p.id] = DocMeta(
                id=p.id,
                corpus_id=p.corpus_id,
                text=text,
                translation=p.translation,
                codes=[t.theme_code for t in p.themes if t.status != "rejected"],
                valence=(p.coding or {}).get("valence"),
                status=p.status,
                needs_review=p.needs_review,
                key=match_key(text),
                tokens={match_key(t) for t in tokenize(text)},
                en_terms=set(english_terms(" ".join(filter(None, [p.translation, (p.coding or {}).get("deeper_meaning")])))),
            )

    def _cached_vectors(self, db: Session, phrases: list[Phrase], docs: list[str], ns: str) -> np.ndarray:
        """Reuse stored embeddings when the document text is unchanged (matters for transformer models)."""
        model = f"{self.embedder.name}:{ns}"
        hashes = [hashlib.sha256(d.encode("utf-8")).hexdigest() for d in docs]
        stored = {
            (e.phrase_id): e
            for e in db.scalars(
                select(PhraseEmbedding).where(
                    PhraseEmbedding.model == model, PhraseEmbedding.phrase_id.in_([p.id for p in phrases])
                )
            )
        }
        missing = [i for i, p in enumerate(phrases) if p.id not in stored or stored[p.id].content_hash != hashes[i]]
        vectors = np.zeros((len(phrases), self.embedder.dim), dtype=np.float32)
        if missing:
            fresh = self.embedder.embed_documents([docs[i] for i in missing])
            for row, i in enumerate(missing):
                vectors[i] = fresh[row]
                pid = phrases[i].id
                if pid in stored:
                    stored[pid].vector = fresh[row].tolist()
                    stored[pid].content_hash = hashes[i]
                else:
                    db.add(PhraseEmbedding(phrase_id=pid, model=model, dim=self.embedder.dim,
                                           vector=fresh[row].tolist(), content_hash=hashes[i]))
            db.commit()
        for i, p in enumerate(phrases):
            if i not in missing:
                vectors[i] = np.asarray(stored[p.id].vector, dtype=np.float32)
        return vectors

    # --- Queries ---------------------------------------------------------------

    def _reasons(self, meta: DocMeta, query_tokens: set[str], query_terms: set[str], themes: dict[str, float]) -> list[str]:
        kb = get_knowledge()
        reasons = []
        shared_themes = [c for c in meta.codes if c in themes]
        if shared_themes:
            reasons.append("Shared theme: " + ", ".join(kb.themes[c]["label_en"] for c in shared_themes if c in kb.themes))
        shared_words = sorted(query_tokens & meta.tokens, key=len, reverse=True)[:4]
        if shared_words:
            reasons.append("Shared words: " + ", ".join(shared_words))
        shared_terms = sorted(query_terms & meta.en_terms)[:4]
        if shared_terms:
            reasons.append("Matches the translation or interpretation: " + ", ".join(shared_terms))
        return reasons

    def search(
        self,
        query: str,
        k: int = 12,
        theme: str | None = None,
        include_missing: bool = True,
    ) -> list[Hit]:
        kb = get_knowledge()
        q_themes = kb.themes_for_query(query)
        vec = self.embedder.embed_query(query)
        raw = self.index.search("full", vec, k=max(k * 4, 40))
        q_tokens = {match_key(t) for t in tokenize(query)}
        q_terms = set(english_terms(query))
        hits: list[Hit] = []
        for pid, vscore in raw:
            meta = self.meta.get(pid)
            if not meta or (theme and theme not in meta.codes):
                continue
            if not include_missing and meta.status == "text_missing":
                continue
            tscore = sum(q_themes.get(c, 0.0) for c in meta.codes) / (sum(q_themes.values()) or 1.0)
            score = 0.7 * max(vscore, 0.0) + 0.3 * tscore
            reasons = self._reasons(meta, q_tokens, q_terms, q_themes)
            if score < 0.08 and not reasons:
                continue
            hits.append(Hit(pid, round(score, 4), round(vscore, 4), round(tscore, 4), reasons, meta))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

    def related(
        self,
        text: str,
        k: int = 5,
        codes: list[str] | None = None,
        exclude: set[int] | None = None,
        min_score: float = 0.12,
    ) -> list[Hit]:
        """Related corpus expressions for a phrase: wording similarity blended with theme overlap."""
        vec = self.embedder.embed_query(text)
        raw = self.index.search("text", vec, k=max(k * 6, 30), exclude=exclude)
        codes_w = {c: 1.0 for c in (codes or [])}
        q_tokens = {match_key(t) for t in tokenize(text)}
        hits: list[Hit] = []
        seen_ids = {pid for pid, _ in raw}
        candidates = list(raw)
        # Theme-only neighbours (different wording, same researcher codes).
        if codes_w:
            for pid, meta in self.meta.items():
                if pid not in seen_ids and (not exclude or pid not in exclude) and set(meta.codes) & set(codes_w):
                    candidates.append((pid, 0.0))
        for pid, vscore in candidates:
            meta = self.meta.get(pid)
            if not meta:
                continue
            overlap = len(set(meta.codes) & set(codes_w))
            tscore = overlap / max(len(codes_w), 1) if codes_w else 0.0
            score = (0.55 * max(vscore, 0.0) + 0.45 * tscore) if codes_w else max(vscore, 0.0)
            if score < min_score:
                continue
            hits.append(Hit(pid, round(score, 4), round(vscore, 4), round(tscore, 4),
                            self._reasons(meta, q_tokens, set(), codes_w), meta))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

    def find_match(self, text: str, threshold: float = 0.86) -> tuple[DocMeta, float] | None:
        """Exact or near-duplicate corpus entry for this text (spelling-tolerant)."""
        key = match_key(text)
        for meta in self.meta.values():
            if meta.key == key:
                return meta, 1.0
        top = self.index.search("text", self.embedder.embed_query(text), k=1)
        if top and top[0][1] >= threshold and top[0][0] in self.meta:
            return self.meta[top[0][0]], round(top[0][1], 4)
        return None


_corpus_index: CorpusIndex | None = None


def get_corpus_index() -> CorpusIndex:
    global _corpus_index
    if _corpus_index is None:
        s = get_settings()
        embedder = make_embedder(s.embedding_provider, s.embedding_model)
        index: VectorIndex
        if s.vector_backend == "pgvector":
            index = PgVectorIndex(db_engine, embedder.dim)
        else:
            index = MemoryVectorIndex()
        _corpus_index = CorpusIndex(embedder, index)
    return _corpus_index
