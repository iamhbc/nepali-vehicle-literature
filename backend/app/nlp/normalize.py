"""Unicode and orthographic normalization for Nepali text.

Two levels:

* :func:`normalize_text` — safe display normalization (NFC, whitespace,
  quotes, stray markup). The result is still the user's text.
* :func:`match_key` — an aggressive, lossy key for matching and retrieval that
  folds common Nepali spelling variation (ि/ी, ु/ू, ँ/ं, ब/व, श/ष/स, ज्ञ
  spellings) and drops punctuation. Never shown to users.
"""

from __future__ import annotations

import re
import unicodedata

ZERO_WIDTH = "\u200b\u200c\u200d\u2060\ufeff"
QUOTE_MAP = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "`": "'"})

# Lossy folds for the match key: (from, to)
_FOLDS = [
    ("ी", "ि"),
    ("ू", "ु"),
    ("ँ", "ं"),
    ("व", "ब"),
    ("श", "स"),
    ("ष", "स"),
    ("ण", "न"),
    ("ङ्", "ं"),
    ("ञ्", "ं"),
    ("न्", "ं"),
    ("म्", "ं"),
    ("ः", ""),
    ("़", ""),
]
_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_SPACES = re.compile(r"\s+")
_DEVANAGARI = re.compile(r"[\u0900-\u097F]")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "")
    text = text.translate(QUOTE_MAP)
    text = re.sub(r"\\([\-!*_.])", r"\1", text)  # markdown escapes from copy-paste
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    # Pipe or ASCII bar used as danda.
    text = re.sub(r"(?<=[\u0900-\u097F])\s*\|\s*", "। ", text)
    return text.strip()


def match_key(text: str) -> str:
    text = normalize_text(text).lower()
    text = "".join(ch for ch in text if ch not in ZERO_WIDTH)
    text = text.replace("।", " ").replace("॥", " ")
    text = text.translate(_DEVANAGARI_DIGITS)
    for src, dst in _FOLDS:
        text = text.replace(src, dst)
    text = "".join(" " if unicodedata.category(ch)[0] in "PS" else ch for ch in text)
    return _SPACES.sub(" ", text).strip()


def tokenize(text: str) -> list[str]:
    """Whitespace/punctuation tokenizer that keeps Devanagari combining marks intact."""
    text = normalize_text(text)
    text = "".join(ch for ch in text if ch not in ZERO_WIDTH)
    text = re.sub(r"[।॥,;:!?\"'()\[\]{}…–—\-/.]", " ", text)
    return [t for t in text.split() if t]


def has_devanagari(text: str) -> bool:
    return bool(_DEVANAGARI.search(text or ""))


def char_ngrams(key: str, sizes: tuple[int, ...] = (2, 3, 4)) -> list[str]:
    grams: list[str] = []
    for word in key.split():
        padded = f" {word} "
        for n in sizes:
            if len(padded) < n:
                continue
            grams.extend(padded[i : i + n] for i in range(len(padded) - n + 1))
    return grams
