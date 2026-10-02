"""Baseline analysis engine: research corpus + lexicon + deterministic rhetoric.

Used when no LLM is configured, when the LLM fails, and as the instant
preliminary reading while the LLM works. It never invents a translation or an
interpretation: unknown phrases get lexical cues and corpus-neighbour
hypotheses, all labelled as such.
"""

from __future__ import annotations

from collections import defaultdict

from ..knowledge import KnowledgeBase, LexiconHit, get_knowledge
from ..nlp.transliterate import transliterate
from ..retrieval.search import DocMeta
from . import rhetoric
from .schema import (
    Ambiguity,
    AnalysisPayload,
    DimensionReading,
    EmotionFinding,
    EmotionReading,
    Finding,
    GenderPowerReading,
    ImpliedMeaning,
    KeyTerm,
    LoveFinding,
    LoveReading,
    RelationshipFinding,
    RelationshipReading,
    ThemeAssignment,
)

POSITIVE_FAMILIES = {"joy", "hope", "pride", "devotion", "compassion"}
NEGATIVE_FAMILIES = {"sorrow", "disillusionment", "anger", "fear", "longing"}
GROUP_TO_DIMENSION = {
    "love": "love", "social": "social", "economic": "economic", "political": "political",
    "gender_power": "gender_power", "cultural": "cultural", "philosophical": "philosophical", "rhetorical": "rhetoric",
}
LOVE_KEYS = {"eros", "ludus", "storge", "philia", "agape", "maya", "viraha", "vatsalya", "bhakti", "unrequited", "conditional"}


def _conf(value: str | None, default: str = "medium") -> str:
    v = (value or "").strip().lower()
    return v if v in ("high", "medium", "low") else default


def _empty(summary: str) -> DimensionReading:
    return DimensionReading(present=False, summary=summary, findings=[])


def _love_key(label: str) -> str:
    low = label.lower()
    for key in LOVE_KEYS:
        if low.startswith(key):
            return "unrequited" if "unrequited" in low else key
    if "conditional" in low:
        return "conditional"
    return "other"


def _evidence_in_text(quotes: list[str], text: str) -> list[str]:
    return [q for q in quotes if q and q in text]


# --- Reading reproduced from the research corpus ---------------------------------------


def from_corpus(text: str, meta: DocMeta, coding: dict, kb: KnowledgeBase) -> AnalysisPayload:
    conf = _conf(coding.get("confidence"))
    evidence = _evidence_in_text(coding.get("evidence") or [], text)
    src = f"From the research corpus coding of {meta.corpus_id} (first pass, pending native-speaker review)."
    intensity = (coding.get("emotion_intensity") or "Moderate").lower()
    intensity = intensity if intensity in ("low", "moderate", "high") else "moderate"

    emotions = [
        EmotionFinding(label=e, family=kb.emotion_family(e) or "other", intensity=intensity,
                       explanation=src, evidence=evidence, confidence=conf, kind="interpretation")
        for e in coding.get("emotions") or []
    ]
    valence = (coding.get("valence") or "neutral").lower()
    loves = [
        LoveFinding(label=l, love_type=_love_key(l), explanation=src, evidence=evidence, confidence=conf, kind="interpretation")
        for l in coding.get("love_types") or [] if l.lower() not in ("ambiguous",)
    ]
    rels = [
        RelationshipFinding(label=r, parties=[], power_relation="not evident", explanation=src,
                            evidence=evidence, confidence=conf, kind="interpretation")
        for r in coding.get("relationship_types") or []
    ]

    by_dim: dict[str, list[Finding]] = defaultdict(list)
    for code in meta.codes:
        theme = kb.themes.get(code)
        if not theme:
            continue
        dim = GROUP_TO_DIMENSION.get(theme["group"], "social")
        by_dim[dim].append(Finding(label=theme["label_en"], explanation=f"{theme['definition']}. {src}",
                                   evidence=evidence, confidence=conf, kind="interpretation"))
    for concept in coding.get("cultural_concepts") or []:
        by_dim["cultural"].append(Finding(label=concept, explanation=src, evidence=[], confidence=conf, kind="interpretation"))
    for device in coding.get("rhetorical_devices") or []:
        by_dim["rhetoric"].append(Finding(label=device, explanation=src, evidence=[], confidence="high", kind="evidence"))
    if coding.get("humor_irony"):
        by_dim["rhetoric"].append(Finding(label="Humour: " + coding["humor_irony"], explanation=src, evidence=[], confidence=conf, kind="interpretation"))

    def dim(key: str, free_text_field: str | None = None) -> DimensionReading:
        findings = by_dim.get(key, [])
        summary = (coding.get(free_text_field) if free_text_field else None) or (
            "; ".join(f.label for f in findings) if findings else "Not evident in the corpus coding."
        )
        return DimensionReading(present=bool(findings) or bool(free_text_field and coding.get(free_text_field)),
                                summary=summary, findings=findings)

    power = coding.get("power_hierarchy") or {}
    stances = [s.lower() for s in power.get("stances") or []]
    gender_findings = by_dim.get("gender_power", [])

    return AnalysisPayload(
        detected_language="ne",
        transliteration="",
        literal_translation=meta.translation or "",
        contextual_translation=meta.translation or "",
        text_types=coding.get("text_types") or [],
        key_terms=[],
        emotion=EmotionReading(
            summary=", ".join(coding.get("emotions") or []) or "Not coded.",
            valence=valence if valence in ("positive", "negative", "mixed", "neutral") else "neutral",
            overall_intensity=intensity,
            targets=coding.get("emotional_targets") or [],
            direction="; ".join(coding.get("emotional_targets") or []) or "not evident",
            findings=emotions,
        ),
        love=LoveReading(present=bool(loves), summary=", ".join(coding.get("love_types") or []) or "No love type coded.", findings=loves),
        relationships=RelationshipReading(present=bool(rels), summary=", ".join(coding.get("relationship_types") or []) or "Not evident.", findings=rels),
        social=dim("social", "identity_theme"),
        economic=dim("economic", "economic_theme"),
        political=dim("political", "political_theme"),
        gender_power=GenderPowerReading(
            present=bool(gender_findings) or bool(coding.get("gender_theme")),
            summary=coding.get("gender_theme") or "Not evident in the corpus coding.",
            power_stance=stances[0] if stances else "not_applicable",
            stance_explanation=power.get("raw") or "No power hierarchy coded.",
            findings=gender_findings,
        ),
        cultural=dim("cultural", "religious_theme"),
        philosophical=dim("philosophical", "temporal_orientation"),
        rhetoric=dim("rhetoric"),
        implied=ImpliedMeaning(
            literal=meta.translation or "",
            implied=coding.get("deeper_meaning") or "",
            cultural_reading="",
            alternatives=[coding["alternative_interpretation"]] if coding.get("alternative_interpretation") else [],
            confidence=conf,
        ),
        themes=[ThemeAssignment(code=c, confidence=conf, rationale=src) for c in meta.codes],
        ambiguity=Ambiguity(is_ambiguous=conf == "low", note=coding.get("alternative_interpretation") or ""),
        context_note="The corpus record has no vehicle, location or date; readings may shift with that context.",
        overall_confidence=conf,
    )


# --- Reading built from lexical cues and corpus neighbours --------------------------------


def from_signals(
    text: str,
    hits: list[LexiconHit],
    neighbours: list[tuple[DocMeta, dict, float]],
    concept_terms: list[KeyTerm],
    kb: KnowledgeBase,
) -> AnalysisPayload:
    grouped: dict[str, dict[str, list[LexiconHit]]] = defaultdict(lambda: defaultdict(list))
    for hit in hits:
        for sig in hit.signals:
            dim, _, label = sig.partition(":")
            grouped[dim][label].append(hit)

    def finding(label: str, dim_hits: list[LexiconHit], dimension_name: str) -> Finding:
        tokens = sorted({h.token for h in dim_hits})
        weak = all(h.weak for h in dim_hits)
        glosses = "; ".join(sorted({f"«{h.token}» ({h.gloss})" for h in dim_hits}))
        return Finding(
            label=label,
            explanation=f"The wording contains {glosses}, a common cue for {label.lower()} in the {dimension_name} dimension. "
            "This is a lexical signal, not a full reading of the phrase.",
            evidence=tokens,
            confidence="low" if weak or len(tokens) == 1 else "medium",
            kind="hypothesis" if weak else "interpretation",
        )

    def dim(key: str, name: str) -> DimensionReading:
        labels = grouped.get(key, {})
        findings = [finding(label, h, name) for label, h in labels.items()]
        if not findings:
            return _empty(f"No lexical cue for the {name} dimension was found.")
        return DimensionReading(present=True, summary="Possible " + ", ".join(f.label.lower() for f in findings) + ".", findings=findings)

    # Emotions: lexical cues first, then families common among the closest corpus neighbours.
    emotions: list[EmotionFinding] = []
    for fam_key, fam_hits in grouped.get("emotion", {}).items():
        fam = kb.emotion_families.get(fam_key, {"label_en": fam_key})
        base = finding(fam["label_en"], fam_hits, "emotional")
        emotions.append(EmotionFinding(**base.model_dump(), family=fam_key, intensity="moderate"))
    neighbour_fams: dict[str, list[str]] = defaultdict(list)
    for meta, coding, score in neighbours[:2]:
        if score < 0.3:
            continue
        for e in coding.get("emotions") or []:
            fam = kb.emotion_family(e)
            if fam:
                neighbour_fams[fam].append(meta.corpus_id)
    for fam_key, ids in sorted(neighbour_fams.items(), key=lambda kv: -len(kv[1]))[:2]:
        if fam_key in {e.family for e in emotions}:
            continue
        fam = kb.emotion_families[fam_key]
        emotions.append(EmotionFinding(
            label=fam["label_en"], family=fam_key, intensity="moderate", evidence=[], confidence="low", kind="hypothesis",
            explanation=f"Similar corpus entries ({', '.join(sorted(set(ids)))}) are coded with {fam['label_en'].lower()}; "
            "this phrase may share it, but no word in it states it.",
        ))
    fams = {e.family for e in emotions if e.kind != "hypothesis"}
    valence = ("mixed" if fams & POSITIVE_FAMILIES and fams & NEGATIVE_FAMILIES
               else "positive" if fams & POSITIVE_FAMILIES
               else "negative" if fams & NEGATIVE_FAMILIES else "neutral")

    loves = []
    for key, love_hits in grouped.get("love", {}).items():
        lt = kb.love_types.get(key, {"label_en": key})
        base = finding(lt["label_en"], love_hits, "love")
        loves.append(LoveFinding(**base.model_dump(), love_type=key))
    rels = []
    for label, rel_hits in grouped.get("relationship", {}).items():
        base = finding(label, rel_hits, "relationship")
        rels.append(RelationshipFinding(**base.model_dump(), parties=[], power_relation="not evident"))

    rhetoric_reading = dim("rhetorical", "rhetorical")
    detected = rhetoric.detect(text)
    rhetoric_reading.findings = detected + [f for f in rhetoric_reading.findings if f.label not in {d.label for d in detected}]
    if rhetoric_reading.findings:
        rhetoric_reading.present = True
        rhetoric_reading.summary = "Formal devices: " + ", ".join(f.label for f in rhetoric_reading.findings) + "."

    # Themes: lexical theme cues + weighted vote of nearest corpus entries.
    votes: dict[str, float] = defaultdict(float)
    voters: dict[str, list[str]] = defaultdict(list)
    for meta, _coding, score in neighbours[:5]:
        for code in meta.codes:
            votes[code] += score
            voters[code].append(meta.corpus_id)
    themes: list[ThemeAssignment] = []
    lexical_codes = grouped.get("theme", {})
    for code, code_hits in lexical_codes.items():
        if code not in kb.themes:
            continue
        tokens = ", ".join(sorted({h.token for h in code_hits}))
        support = f" Also shared by similar corpus entries ({', '.join(voters[code][:3])})." if code in voters else ""
        themes.append(ThemeAssignment(
            code=code, confidence="medium" if code in voters or len(code_hits) > 1 else "low",
            rationale=f"Lexical cue: {tokens}.{support}",
        ))
    for code, weight in sorted(votes.items(), key=lambda kv: -kv[1]):
        if code in lexical_codes or weight < 0.45:
            continue
        themes.append(ThemeAssignment(
            code=code, confidence="low",
            rationale=f"Hypothesis from similar corpus entries ({', '.join(voters[code][:3])}); no direct lexical cue.",
        ))

    gender = dim("gender_power", "gender and power")
    alternatives = [
        f"A similar corpus entry ({meta.corpus_id}) is read as: {coding['deeper_meaning']}"
        for meta, coding, score in neighbours[:2] if coding.get("deeper_meaning") and score >= 0.3
    ]
    lexicon_note = "Interpretive translation and implied meaning need the LLM engine; this baseline reports surface cues only."
    return AnalysisPayload(
        detected_language="ne",
        transliteration=transliterate(text),
        literal_translation="",
        contextual_translation="",
        text_types=[],
        key_terms=concept_terms,
        emotion=EmotionReading(
            summary=("Possible " + ", ".join(e.label.lower() for e in emotions) + ".") if emotions else "No emotional cue words were found.",
            valence=valence, overall_intensity="moderate", targets=[], direction="not determined", findings=emotions,
        ),
        love=LoveReading(present=bool(loves), summary=("Cues for " + ", ".join(l.label for l in loves) + ".") if loves else "No love vocabulary was found.", findings=loves),
        relationships=RelationshipReading(present=bool(rels), summary=("Cues for " + ", ".join(r.label for r in rels) + ".") if rels else "No relationship vocabulary was found.", findings=rels),
        social=dim("social", "social"),
        economic=dim("economic", "economic"),
        political=dim("political", "political"),
        gender_power=GenderPowerReading(
            present=gender.present, summary=gender.summary,
            power_stance="ambiguous" if gender.present else "not_applicable",
            stance_explanation="A power stance cannot be judged from word cues alone." if gender.present else "No gender or power vocabulary was found.",
            findings=gender.findings,
        ),
        cultural=dim("cultural", "cultural"),
        philosophical=dim("philosophical", "philosophical"),
        rhetoric=rhetoric_reading,
        implied=ImpliedMeaning(literal="", implied="", cultural_reading="", alternatives=alternatives, confidence="low"),
        themes=themes,
        ambiguity=Ambiguity(is_ambiguous=True, note=lexicon_note),
        context_note="The meaning of painted inscriptions often depends on the vehicle, the route and who reads them.",
        overall_confidence="low",
    )


def concept_key_terms(text: str, kb: KnowledgeBase | None = None) -> list[KeyTerm]:
    kb = kb or get_knowledge()
    terms = []
    for hit in kb.match_concepts(text):
        c = kb.concepts_by_slug[hit.slug]
        terms.append(KeyTerm(term=hit.token, transliteration=c["translit"], gloss=c["gloss"],
                             note=c["explanation"], culturally_specific=True))
    return terms

