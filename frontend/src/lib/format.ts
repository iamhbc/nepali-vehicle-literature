const NE_DIGITS = ["०", "१", "२", "३", "४", "५", "६", "७", "८", "९"];

export const toNepaliDigits = (value: number | string): string =>
  String(value).replace(/[0-9]/g, (d) => NE_DIGITS[Number(d)]);

/** "NVL-021" → { prefix: "NVL", number: "०२१" } for number-plate display. */
export function plateParts(corpusId: string): { prefix: string; number: string } {
  const [prefix, num] = corpusId.split("-");
  return { prefix: prefix ?? corpusId, number: num ? toNepaliDigits(num) : "" };
}

export const pct = (x: number) => `${Math.round(x * 100)}%`;

export const titleCase = (s: string) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export const DIMENSION_LABELS: Record<string, { en: string; ne: string }> = {
  emotion: { en: "Emotion", ne: "भावना" },
  love: { en: "Love", ne: "माया" },
  relationship: { en: "Relationship", ne: "सम्बन्ध" },
  social: { en: "Social", ne: "समाज" },
  economic: { en: "Economic", ne: "अर्थ" },
  political: { en: "Political", ne: "राजनीति" },
  gender_power: { en: "Gender & Power", ne: "लैङ्गिकता र शक्ति" },
  cultural: { en: "Cultural", ne: "संस्कृति" },
  philosophical: { en: "Philosophical", ne: "दर्शन" },
  rhetoric: { en: "Rhetoric & Humour", ne: "शैली र हास्य" },
  themes: { en: "Codebook themes", ne: "विषय" },
  concepts: { en: "Cultural concepts", ne: "अवधारणा" },
  related: { en: "Related expressions", ne: "सम्बन्धित" },
};

export const dimColor = (dim?: string | null) => `var(--dim-${dim ?? "related"})`;

export const KIND_LABELS = {
  evidence: { en: "Evidence", hint: "What the words literally say." },
  interpretation: { en: "Interpretation", hint: "What the analysis infers from the wording." },
  hypothesis: { en: "Hypothesis", hint: "What may be implied; plausible but not established." },
} as const;
