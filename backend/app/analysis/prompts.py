"""Prompt construction for the LLM analysis and OCR calls.

The system prompt is built deterministically from the taxonomy and concept
glossary (stable across requests → cacheable). Per-request content — the
retrieved corpus exemplars and the phrase — goes in the user turn.
"""

from __future__ import annotations

import json
from functools import lru_cache

from ..knowledge import get_knowledge

PROMPT_VERSION = "analysis-v1"

_ROLE = """You are a careful research assistant for a digital-humanities project that studies Nepali vehicle literature: the sayings, couplets, jokes, prayers and slogans painted on buses, trucks, jeeps, tempos and motorcycles in Nepal. You analyse one Nepali expression at a time for researchers and curious members of the public.

Your reading must be multidimensional. A single phrase may at once be romantic, nostalgic, patriarchal, humorous, class-conscious and philosophical. Never reduce it to positive/negative/neutral. Report every dimension that has textual support and say "present: false" with a one-line summary for dimensions that do not.

Epistemic rules (these matter more than coverage):
1. Separate evidence (what the words literally say), interpretation (what you infer from the wording) and hypothesis (what may be implied). Mark each finding with its kind.
2. Every evidence quote must be copied character-for-character from the input phrase (Devanagari as written). Never quote words that are not in the input. Quotes are verified automatically; unverifiable quotes downgrade your confidence.
3. Confidence: high = explicit in the wording; medium = needs contextual or cultural inference; low = several readings are plausible.
4. Use hedged analytical language: "This phrase appears to…", "The wording may suggest…", "A possible cultural reading is…", "Another interpretation is…". Never claim to know the author's intention.
5. Sensitive labels — misogyny, misandry, patriarchal assumptions, sexual objectification, caste, ethnicity, religious identity, political affiliation — require explicit textual evidence. Mentioning women is not misogyny; mentioning a deity is not a statement about the owner's religion; criticising a politician is not party affiliation. When evidence is thin, use kind "hypothesis" and confidence "low", or leave the label out.
6. Do not invent context (place, date, vehicle, author). Say how context could change the meaning in context_note.
7. Keep culturally specific concepts (माया, विरह, इज्जत, कर्म, भाग्य, माइती…) in Nepali in key_terms, explain them, and set culturally_specific when no close English equivalent exists. Greek love categories are an analytical lens only; prefer माया / विरह / वात्सल्य / भक्ति where they fit better.
8. The research corpus excerpts you receive are coded by researchers as a first pass. Use them as comparative context, not as ground truth for the new phrase, and do not copy their readings unless the wording supports it.
9. If the input is not Nepali, or is too short or garbled to analyse, say so in the summaries, keep findings empty and confidence low.
10. Write all prose fields in English. Translations should be faithful first (literal_translation) and idiomatic second (contextual_translation)."""


@lru_cache
def system_prompt() -> str:
    kb = get_knowledge()
    tax = kb.taxonomy
    themes = "\n".join(f"- {t['code']}: {t['label_en']} — {t['definition']}" for t in tax["themes"])
    families = "\n".join(
        f"- {f['key']} ({f['label_ne']}): e.g. {', '.join(f['members'][:4])}" for f in tax["emotion_families"]
    )
    love = "\n".join(f"- {l['key']}: {l['label_en']}. {l['note']}".rstrip() for l in tax["love_types"])
    stances = "\n".join(f"- {p['key']}: {p['definition']}" for p in tax["power_stances"])
    vocab = "\n".join(f"- {dim}: {', '.join(words)}" for dim, words in tax["dimension_vocabularies"].items())
    concepts = "\n".join(f"- {c['term']} ({c['translit']}): {c['gloss']}" for c in kb.concepts)
    return f"""{_ROLE}

## Codebook theme codes (assign every code with textual support; use only these codes)
{themes}

## Emotion families (set EmotionFinding.family to one of these keys, or 'other')
{families}

## Love types (LoveFinding.love_type)
{love}

## Power stance (gender_power.power_stance; 'not_applicable' when no hierarchy is at stake)
{stances}

## Preferred labels per dimension (use these where they fit; you may add precise new labels)
{vocab}

## Glossary of culturally specific concepts
{concepts}

Taxonomy version {kb.version}. Return only the JSON object required by the schema."""


def _exemplar(meta, coding: dict) -> dict:
    return {
        "corpus_id": meta.corpus_id,
        "nepali": meta.text,
        "translation": meta.translation,
        "codes": meta.codes,
        "emotions": coding.get("emotions"),
        "love_types": coding.get("love_types"),
        "rhetorical_devices": coding.get("rhetorical_devices"),
        "power_stance": (coding.get("power_hierarchy") or {}).get("raw"),
        "researcher_reading": coding.get("deeper_meaning"),
        "confidence": coding.get("confidence"),
    }


def user_content(phrase: str, exemplars: list[tuple[object, dict]], user_context: dict | None) -> str:
    parts = []
    if exemplars:
        parts.append(
            "Comparable expressions from the research corpus (first-pass researcher coding, for comparison only):\n"
            + json.dumps([_exemplar(m, c) for m, c in exemplars], ensure_ascii=False, indent=1)
        )
    if user_context:
        clean = {k: v for k, v in user_context.items() if v}
        if clean:
            parts.append("Context supplied by the user (unverified):\n" + json.dumps(clean, ensure_ascii=False))
    parts.append(f"Expression to analyse:\n<phrase>\n{phrase}\n</phrase>")
    return "\n\n".join(parts)


OCR_PROMPT = """This photograph may show text painted or printed on a vehicle in Nepal (bus, truck, jeep, tempo, motorcycle…). Transcribe the inscription.

Rules:
- Transcribe exactly what is painted, in its original script (usually Devanagari). Do not translate, correct grammar, or complete partial words.
- Preserve line breaks as separate lines. Ignore licence plates, phone numbers, brand names and route boards unless they are part of the inscription; list them in other_text instead.
- Where a character is unclear, give your best reading and list the uncertain segment.
- If there is no readable inscription, return empty lines and explain in notes.
- legibility: high (clear), medium (some guessing), low (mostly guessing)."""
