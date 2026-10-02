"""Structured analysis contract.

``AnalysisPayload`` is what an analysis engine produces (the LLM fills it via
JSON-schema-constrained output; the baseline engine builds it directly).
``AnalysisResult`` wraps it with retrieval, verification, references and the
graph, and is what the API returns.

Every interpretive claim is a ``Finding`` with evidence, confidence and an
epistemic kind, so the UI can always separate what the phrase *says* from what
the analysis *infers*.
"""

from __future__ import annotations

import copy
from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]
Kind = Literal["evidence", "interpretation", "hypothesis"]
Valence = Literal["positive", "negative", "mixed", "neutral"]
Intensity = Literal["low", "moderate", "high"]
PowerStance = Literal["reproduction", "reflection", "critique", "resistance", "ambiguous", "not_applicable"]


class Finding(BaseModel):
    label: str = Field(description="Short label, preferably from the taxonomy vocabulary for this dimension.")
    explanation: str = Field(description="Why this label applies, in hedged analytical language ('The wording may suggest…').")
    evidence: list[str] = Field(description="Verbatim quotes copied exactly from the input phrase. Empty only for hypotheses.")
    confidence: Confidence
    kind: Kind = Field(description="evidence = literally stated; interpretation = inferred from wording; hypothesis = possible implication.")


class EmotionFinding(Finding):
    family: str = Field(description="Emotion family key from the taxonomy, or 'other'.")
    intensity: Intensity


class LoveFinding(Finding):
    love_type: str = Field(description="Love type key from the taxonomy (maya, viraha, eros, ludus, storge, vatsalya, philia, agape, bhakti, unrequited, conditional) or 'other'.")


class RelationshipFinding(Finding):
    parties: list[str] = Field(description="Who is related, e.g. ['speaker (driver)', 'passenger'].")
    power_relation: str = Field(description="How power is distributed between the parties, or 'not evident'.")


class DimensionReading(BaseModel):
    present: bool
    summary: str
    findings: list[Finding]


class EmotionReading(BaseModel):
    summary: str
    valence: Valence
    overall_intensity: Intensity
    targets: list[str] = Field(description="Toward whom/what the emotion is directed.")
    direction: str = Field(description="e.g. 'speaker → former lover', 'speaker → society'.")
    findings: list[EmotionFinding]


class LoveReading(BaseModel):
    present: bool
    summary: str
    findings: list[LoveFinding]


class RelationshipReading(BaseModel):
    present: bool
    summary: str
    findings: list[RelationshipFinding]


class GenderPowerReading(BaseModel):
    present: bool
    summary: str
    power_stance: PowerStance
    stance_explanation: str
    findings: list[Finding]


class KeyTerm(BaseModel):
    term: str = Field(description="Word or phrase exactly as in the input.")
    transliteration: str
    gloss: str
    note: str = Field(description="Cultural or grammatical note; empty if none.")
    culturally_specific: bool = Field(description="True if the term has no close one-to-one English equivalent.")


class ImpliedMeaning(BaseModel):
    literal: str = Field(description="What the phrase explicitly says.")
    implied: str = Field(description="What it may communicate beyond the literal wording.")
    cultural_reading: str = Field(description="Cultural assumptions that may be embedded.")
    alternatives: list[str] = Field(description="Other plausible readings.")
    confidence: Confidence


class ThemeAssignment(BaseModel):
    code: str = Field(description="A theme code from the codebook.")
    confidence: Confidence
    rationale: str


class Ambiguity(BaseModel):
    is_ambiguous: bool
    note: str


class AnalysisPayload(BaseModel):
    detected_language: str
    transliteration: str
    literal_translation: str
    contextual_translation: str
    text_types: list[str]
    key_terms: list[KeyTerm]
    emotion: EmotionReading
    love: LoveReading
    relationships: RelationshipReading
    social: DimensionReading
    economic: DimensionReading
    political: DimensionReading
    gender_power: GenderPowerReading
    cultural: DimensionReading
    philosophical: DimensionReading
    rhetoric: DimensionReading
    implied: ImpliedMeaning
    themes: list[ThemeAssignment]
    ambiguity: Ambiguity
    context_note: str = Field(description="How meaning could change with context (vehicle, place, who wrote it).")
    overall_confidence: Confidence


# --- API response ----------------------------------------------------------------


class EngineInfo(BaseModel):
    mode: Literal["llm", "baseline"]
    model: str | None = None
    effort: str | None = None
    taxonomy_version: str
    prompt_version: str
    duration_ms: int | None = None
    cached: bool = False
    notes: list[str] = []


class RelatedEntry(BaseModel):
    id: int
    corpus_id: str
    text: str
    translation: str | None
    score: float
    reasons: list[str]
    codes: list[str]
    needs_review: bool
    status: str


class CorpusMatch(BaseModel):
    id: int
    corpus_id: str
    similarity: float
    exact: bool
    text: str
    translation: str | None
    codes: list[str]
    coding: dict
    needs_review: bool
    review_reason: str | None


class ConceptNote(BaseModel):
    slug: str
    term: str
    translit: str
    gloss: str
    explanation: str
    surface: str
    references: list[str]


class LexicalSignal(BaseModel):
    token: str
    gloss: str
    signals: list[str]
    weak: bool
    reflected_in_reading: bool = True


class ReferenceOut(BaseModel):
    id: str
    title: str
    authors: str
    year: int | None
    source: str
    url: str | None
    kind: str
    level: int
    matched_topics: list[str]
    note: str | None = None


class VerificationIssue(BaseModel):
    dimension: str
    label: str
    quote: str
    action: str


class Verification(BaseModel):
    findings_checked: int
    quotes_checked: int
    quotes_verified: int
    issues: list[VerificationIssue]


class GraphNode(BaseModel):
    id: str
    label: str
    label_ne: str | None = None
    type: Literal["root", "dimension", "finding", "theme", "concept", "related"]
    dimension: str | None = None
    confidence: Confidence | None = None
    kind: Kind | None = None
    detail: dict = {}


class GraphEdge(BaseModel):
    source: str
    target: str
    weight: float = 1.0


class Graph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class AnalysisResult(BaseModel):
    id: str
    created_at: str
    input_text: str
    normalized_text: str
    language: dict
    engine: EngineInfo
    payload: AnalysisPayload
    corpus_match: CorpusMatch | None
    related: list[RelatedEntry]
    concepts: list[ConceptNote]
    lexical_signals: list[LexicalSignal]
    references: list[ReferenceOut]
    verification: Verification
    graph: Graph
    warnings: list[str]


# --- JSON schema for constrained decoding ------------------------------------------

_UNSUPPORTED = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
                "minLength", "maxLength", "pattern", "minItems", "maxItems", "default", "title"}


def strict_json_schema(model: type[BaseModel]) -> dict:
    """Pydantic schema → strict structured-output schema (all fields required, no extras)."""
    schema = copy.deepcopy(model.model_json_schema())

    def walk(node, is_property_map: bool = False):
        if isinstance(node, dict):
            if not is_property_map:
                for key in list(node):
                    if key in _UNSUPPORTED:
                        node.pop(key)
                if node.get("type") == "object" and "properties" in node:
                    node["additionalProperties"] = False
                    node["required"] = list(node["properties"].keys())
            for key, value in node.items():
                walk(value, is_property_map=(key in ("properties", "$defs") and not is_property_map))
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    return schema
