"""In-process access to the research knowledge layer (taxonomy, lexicon, concepts, references).

These files are small, versioned with the code, and read once at startup.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .config import get_settings
from .nlp.normalize import match_key, tokenize

# Nepali postpositions / plural / emphatic endings allowed after a lexicon form.
SUFFIXES = sorted(
    {
        "लाई", "को", "का", "की", "मा", "ले", "बाट", "सँग", "संग", "भन्दा", "देखि", "तिर", "सम्म",
        "हरू", "हरु", "हरूको", "हरूका", "हरूलाई", "हरूले", "हरूमा", "कै", "कि", "मै", "लाइ",
        "नै", "ैँ", "भरि", "भर", "वाला", "जस्तो", "झैँ", "पनि", "त", "ई", "ी",
    },
    key=len,
    reverse=True,
)


@dataclass
class LexiconHit:
    token: str
    form: str
    gloss: str
    signals: list[str]
    weak: bool


@dataclass
class ConceptHit:
    slug: str
    term: str
    token: str


@dataclass
class KnowledgeBase:
    taxonomy: dict
    lexicon: list[dict]
    concepts: list[dict]
    references: list[dict]
    themes: dict[str, dict] = field(init=False)
    emotion_family_of: dict[str, str] = field(init=False)

    def __post_init__(self) -> None:
        self.themes = {t["code"]: t for t in self.taxonomy["themes"]}
        self.emotion_family_of = {}
        for fam in self.taxonomy["emotion_families"]:
            for member in fam["members"]:
                self.emotion_family_of[member.lower()] = fam["key"]
        self.emotion_families = {f["key"]: f for f in self.taxonomy["emotion_families"]}
        self.love_types = {l["key"]: l for l in self.taxonomy["love_types"]}
        self.dimensions = {d["key"]: d for d in self.taxonomy["dimensions"]}
        self.concepts_by_slug = {c["slug"]: c for c in self.concepts}
        self.references_by_id = {r["id"]: r for r in self.references}
        self._theme_terms = self._build_theme_terms()

    def add_theme(self, theme: dict) -> None:
        """Register a researcher-created theme at runtime (persisted in the database)."""
        if theme["code"] not in self.themes:
            theme.setdefault("keywords_en", [])
            theme.setdefault("keywords_ne", [])
            self.taxonomy["themes"].append(theme)
            self.__post_init__()

    def add_reference(self, ref: dict) -> None:
        self.references = [r for r in self.references if r["id"] != ref["id"]] + [ref]
        self.references_by_id[ref["id"]] = ref

    @property
    def version(self) -> str:
        return self.taxonomy["version"]

    # --- Lexical matching ---------------------------------------------------

    @staticmethod
    def _form_matches(token: str, form: str, prefix: bool) -> bool:
        if token == form:
            return True
        if not token.startswith(form):
            return False
        if prefix:
            return True
        rest = token[len(form):]
        return any(rest == s or rest.startswith(s) and rest[len(s):] in SUFFIXES for s in SUFFIXES)

    def match_lexicon(self, text: str) -> list[LexiconHit]:
        tokens = tokenize(text)
        lowered = [t.lower() for t in tokens]
        hits: list[LexiconHit] = []
        seen: set[tuple[str, str]] = set()
        for entry in self.lexicon:
            prefix = entry.get("prefix", False)
            for form in entry["forms"]:
                f = form.lower()
                for tok, low in zip(tokens, lowered):
                    if self._form_matches(low, f, prefix) and (tok, form) not in seen:
                        seen.add((tok, form))
                        signals = [s.lstrip("~") for s in entry["signals"]]
                        weak = all(s.startswith("~") for s in entry["signals"])
                        hits.append(LexiconHit(tok, form, entry["gloss"], signals, weak))
        return hits

    def match_concepts(self, text: str) -> list[ConceptHit]:
        tokens = tokenize(text)
        found: dict[str, ConceptHit] = {}
        for concept in self.concepts:
            for form in concept["forms"]:
                for tok in tokens:
                    if concept["slug"] not in found and self._form_matches(tok, form, False):
                        found[concept["slug"]] = ConceptHit(concept["slug"], concept["term"], tok)
        return list(found.values())

    # --- Query expansion -------------------------------------------------------

    def _build_theme_terms(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for theme in self.taxonomy["themes"]:
            for kw in theme.get("keywords_en", []) + [theme["label_en"].lower()]:
                pairs.append((kw.lower(), theme["code"]))
            for kw in theme.get("keywords_ne", []):
                pairs.append((match_key(kw), theme["code"]))
        return pairs

    def themes_for_query(self, query: str) -> dict[str, float]:
        """Map a free-text query (English or Nepali) onto theme codes with weights."""
        q_en = " " + re.sub(r"[^a-z\s-]", " ", query.lower()) + " "
        q_ne = " " + match_key(query) + " "
        weights: dict[str, float] = {}
        for term, code in self._theme_terms:
            if not term:
                continue
            haystack = q_ne if re.search(r"[ऀ-ॿ]", term) else q_en
            # Whole-word match, tolerant of simple English plurals.
            if re.search(rf"(?<![a-zऀ-ॿ]){re.escape(term)}(s|es)?(?![a-z])", haystack):
                weights[code] = weights.get(code, 0.0) + (1.0 + 0.15 * len(term.split()))
        if not weights:
            return {}
        top = max(weights.values())
        return {code: round(w / top, 3) for code, w in weights.items()}

    # --- References --------------------------------------------------------------

    def references_for(self, topics: set[str]) -> list[dict]:
        lowered = {t.lower() for t in topics}
        out = []
        for ref in self.references:
            matched = [t for t in ref.get("topics", []) if t.lower() in lowered]
            if matched:
                out.append({**ref, "matched_topics": matched, "level": 2})
        return out

    def emotion_family(self, label: str) -> str | None:
        key = label.strip().lower()
        if key in self.emotion_families:
            return key
        return self.emotion_family_of.get(key)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache
def get_knowledge() -> KnowledgeBase:
    s = get_settings()
    return KnowledgeBase(
        taxonomy=_load(s.taxonomy_path),
        lexicon=_load(s.knowledge_dir / "lexicon.json")["entries"],
        concepts=_load(s.knowledge_dir / "cultural_concepts.json")["concepts"],
        references=_load(s.knowledge_dir / "references.json")["references"],
    )
