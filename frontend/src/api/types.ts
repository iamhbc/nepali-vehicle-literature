// Mirrors backend/app/analysis/schema.py and the API read models.

export type Confidence = "high" | "medium" | "low";
export type Kind = "evidence" | "interpretation" | "hypothesis";
export type Valence = "positive" | "negative" | "mixed" | "neutral";

export interface Finding {
  label: string;
  explanation: string;
  evidence: string[];
  confidence: Confidence;
  kind: Kind;
  family?: string;
  intensity?: string;
  love_type?: string;
  parties?: string[];
  power_relation?: string;
}

export interface DimensionReading {
  present: boolean;
  summary: string;
  findings: Finding[];
}

export interface EmotionReading {
  summary: string;
  valence: Valence;
  overall_intensity: string;
  targets: string[];
  direction: string;
  findings: Finding[];
}

export interface GenderPowerReading extends DimensionReading {
  power_stance: "reproduction" | "reflection" | "critique" | "resistance" | "ambiguous" | "not_applicable";
  stance_explanation: string;
}

export interface KeyTerm {
  term: string;
  transliteration: string;
  gloss: string;
  note: string;
  culturally_specific: boolean;
}

export interface AnalysisPayload {
  detected_language: string;
  transliteration: string;
  literal_translation: string;
  contextual_translation: string;
  text_types: string[];
  key_terms: KeyTerm[];
  emotion: EmotionReading;
  love: DimensionReading;
  relationships: DimensionReading;
  social: DimensionReading;
  economic: DimensionReading;
  political: DimensionReading;
  gender_power: GenderPowerReading;
  cultural: DimensionReading;
  philosophical: DimensionReading;
  rhetoric: DimensionReading;
  implied: { literal: string; implied: string; cultural_reading: string; alternatives: string[]; confidence: Confidence };
  themes: { code: string; confidence: Confidence; rationale: string }[];
  ambiguity: { is_ambiguous: boolean; note: string };
  context_note: string;
  overall_confidence: Confidence;
}

export interface RelatedEntry {
  id: number;
  corpus_id: string;
  text: string;
  translation: string | null;
  score: number;
  reasons: string[];
  codes: string[];
  needs_review?: boolean;
  status?: string;
}

export interface GraphNode {
  id: string;
  label: string;
  label_ne?: string | null;
  type: "root" | "dimension" | "finding" | "theme" | "concept" | "related";
  dimension?: string | null;
  confidence?: Confidence | null;
  kind?: Kind | null;
  detail: Record<string, unknown>;
}

export interface Graph {
  nodes: GraphNode[];
  edges: { source: string; target: string; weight: number }[];
}

export interface Reference {
  id: string;
  title: string;
  authors: string;
  year: number | null;
  source: string;
  url: string | null;
  kind: string;
  level: number;
  matched_topics: string[];
  note?: string | null;
}

export interface ConceptNote {
  slug: string;
  term: string;
  translit: string;
  gloss: string;
  explanation: string;
  surface: string;
}

export interface AnalysisResult {
  id: string;
  created_at: string;
  input_text: string;
  normalized_text: string;
  language: { script: string; language: string; confidence: number; note?: string | null };
  engine: {
    mode: "llm" | "baseline";
    model: string | null;
    effort: string | null;
    taxonomy_version: string;
    prompt_version: string;
    duration_ms: number | null;
    cached: boolean;
    notes: string[];
  };
  payload: AnalysisPayload;
  corpus_match: {
    id: number;
    corpus_id: string;
    similarity: number;
    exact: boolean;
    text: string;
    translation: string | null;
    codes: string[];
    coding: Record<string, unknown>;
    needs_review: boolean;
    review_reason: string | null;
  } | null;
  related: RelatedEntry[];
  concepts: ConceptNote[];
  lexical_signals: { token: string; gloss: string; signals: string[]; weak: boolean; reflected_in_reading: boolean }[];
  references: Reference[];
  verification: {
    findings_checked: number;
    quotes_checked: number;
    quotes_verified: number;
    issues: { dimension: string; label: string; quote: string; action: string }[];
  };
  graph: Graph;
  warnings: string[];
  submission_id?: string;
}

export interface StageEvent {
  stage: string;
  message: string;
  [key: string]: unknown;
}

export interface Theme {
  code: string;
  label_en: string;
  label_ne: string;
  group: string;
  origin: string;
  definition: string;
  count?: number;
}

export interface Meta {
  engine: "llm" | "baseline";
  ocr_available: boolean;
  max_phrase_chars: number;
  taxonomy_version: string;
  themes: Theme[];
  dimensions: { key: string; label_en: string; label_ne: string }[];
  emotion_families: { key: string; label_en: string; label_ne: string }[];
  confidence_levels: Record<Confidence, string>;
  epistemic_kinds: Record<string, string>;
}

export interface PhraseSummary {
  id: number;
  corpus_id: string;
  status: string;
  text: string;
  text_is_candidate: boolean;
  transliteration: string | null;
  translation: string | null;
  codes: string[];
  valence: string | null;
  emotions: string[];
  text_types: string[];
  confidence: string | null;
  needs_review: boolean;
  review_priority: string | null;
  clusters: string[];
  variant_group: string | null;
  vehicle_type: string | null;
  district: string | null;
  places_mentioned: { district: string; surface: string }[];
  source: string;
}

export interface PhraseDetail extends PhraseSummary {
  text_original: string;
  text_candidate: string | null;
  transliteration_original: string | null;
  transliteration_auto: string | null;
  translation_original: string | null;
  translation_normalized: string | null;
  original_theme: string[];
  coding: Record<string, any>;
  themes: { code: string; source: string; status: string; confidence: string | null; rationale: string | null; label_en?: string }[];
  labels: { id: number; dimension: string; label: string; source: string; status: string; confidence: string | null }[];
  review_reason: string | null;
  qc_flags: { check: string; finding: string }[];
  variants: { id: number; corpus_id: string; text: string; relation: string | null }[];
  provenance: Record<string, unknown>;
  related: RelatedEntry[];
  concepts: (ConceptNote & { references: string[] })[];
  graph: Graph | null;
  updated_by: string | null;
  updated_at: string | null;
}

export interface SearchResponse {
  query: string;
  interpreted_themes: { code: string; label_en: string; weight: number }[];
  embedding: string;
  results: (RelatedEntry & { vector_score: number; theme_score: number })[];
  note: string | null;
}

export interface Stats {
  total: number;
  needs_review: number;
  text_missing: number;
  analyses_run: number;
  submissions_pending: number;
  themes: (Theme & { count: number })[];
  emotion_families: { key: string; label_en: string; label_ne?: string; count: number }[];
  emotions: { label: string; count: number }[];
  valence: { label: string; count: number }[];
  love_types: { key: string; label_en: string; count: number }[];
  power_stances: { label: string; count: number }[];
  text_types: { label: string; count: number }[];
  cooccurrence: { source: string; target: string; count: number }[] | null;
  clusters: { name: string; count: number }[];
  vehicles: { slug: string; count: number }[];
  geography: {
    observed: { district: string; province: string | null; count: number }[];
    mentioned: { district: string; province: string | null; count: number }[];
  };
}

export interface Province {
  id: number;
  name_en: string;
  name_ne: string;
  districts: { id: number; name_en: string; name_ne: string }[];
}

export interface VehicleType {
  id: number;
  slug: string;
  name_en: string;
  name_ne: string;
}

export interface OCRResponse {
  text: string;
  lines: { text: string; confidence: Confidence }[];
  legibility: Confidence;
  uncertain_segments: string[];
  other_text: string[];
  notes: string;
  provider: string;
  readable: boolean;
  suggestions: { id: number; corpus_id: string; text: string; similarity: number; reason: string }[];
  image: { width: number; height: number; metadata_stripped: boolean; stored: boolean };
}

export interface AnalyzeContext {
  vehicle_type?: string | null;
  province_id?: number | null;
  district_id?: number | null;
  locality?: string | null;
}
