"""Script and language detection for short Nepali / English / romanized-Nepali input."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

# High-frequency function words of romanized Nepali that are rare in English.
_ROMAN_NEPALI = {
    "ma", "timi", "tapai", "hajur", "ho", "hoina", "chha", "cha", "chhan", "chan", "chhu", "chu",
    "ta", "ni", "ra", "pani", "maya", "mero", "timro", "hamro", "garna", "garchu", "garchha",
    "bhanne", "bhane", "huncha", "hunchha", "thiyo", "kina", "kaha", "kasari", "aba", "sanga",
    "lai", "ko", "ki", "ka", "le", "ma", "bata", "dekhi", "sathi", "aama", "buba", "jindagi",
    "paisa", "gadi", "bato", "dai", "didi", "kanchhi", "yaad", "yad", "parkhi", "nai", "hai",
}
_ENGLISH = {
    "the", "and", "is", "are", "of", "to", "in", "you", "my", "love", "life", "i", "it", "for",
    "with", "that", "this", "be", "not", "on", "me", "your", "we", "they", "what", "who",
}


@dataclass
class LanguageGuess:
    script: str  # devanagari | latin | mixed | other | empty
    language: str  # ne | ne-Latn | en | mixed | unknown
    confidence: float
    devanagari_ratio: float
    note: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def detect_language(text: str) -> LanguageGuess:
    letters = [ch for ch in text if ch.isalpha() or "ऀ" <= ch <= "ॿ"]
    if not letters:
        return LanguageGuess("empty", "unknown", 0.0, 0.0, "No letters found.")
    deva = sum("ऀ" <= ch <= "ॿ" for ch in letters)
    latin = sum(ch.isascii() and ch.isalpha() for ch in letters)
    ratio = deva / len(letters)

    if ratio >= 0.85:
        return LanguageGuess("devanagari", "ne", round(0.9 + 0.1 * ratio, 2), round(ratio, 2))
    if ratio >= 0.3:
        return LanguageGuess(
            "mixed", "mixed", 0.7, round(ratio, 2),
            "Devanagari with embedded Latin script (likely code-mixing).",
        )
    if latin / len(letters) < 0.5:
        return LanguageGuess("other", "unknown", 0.3, round(ratio, 2), "Script not recognised.")

    words = re.findall(r"[a-zA-Z]+", text.lower())
    ne_hits = sum(w in _ROMAN_NEPALI for w in words)
    en_hits = sum(w in _ENGLISH for w in words)
    if ne_hits > en_hits:
        conf = min(0.95, 0.5 + 0.1 * (ne_hits - en_hits))
        return LanguageGuess(
            "latin", "ne-Latn", round(conf, 2), round(ratio, 2),
            "Romanized Nepali. Analysis works best on Devanagari text.",
        )
    conf = min(0.95, 0.5 + 0.1 * (en_hits - ne_hits)) if en_hits else 0.4
    return LanguageGuess(
        "latin", "en", round(conf, 2), round(ratio, 2),
        "This looks like English. The platform is built for Nepali expressions.",
    )
