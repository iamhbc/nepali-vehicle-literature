"""Rule-based Devanagari → IAST transliteration with Nepali schwa deletion.

This is an automatic, approximate romanization intended for readability. It
applies word-final schwa deletion (मन → man, गाडी → gāḍī) but not the
word-medial deletions native speakers make, so long words may keep an extra
'a'. Researcher-entered transliterations always take precedence.
"""

from __future__ import annotations

import re

VOWELS = {
    "अ": "a", "आ": "ā", "इ": "i", "ई": "ī", "उ": "u", "ऊ": "ū", "ऋ": "r̥",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ॠ": "r̥̄", "ऍ": "ê", "ऑ": "ô",
}
MATRAS = {
    "ा": "ā", "ि": "i", "ी": "ī", "ु": "u", "ू": "ū", "ृ": "r̥", "ॄ": "r̥̄",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ॅ": "ê", "ॉ": "ô",
}
CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "ṅ",
    "च": "c", "छ": "ch", "ज": "j", "झ": "jh", "ञ": "ñ",
    "ट": "ṭ", "ठ": "ṭh", "ड": "ḍ", "ढ": "ḍh", "ण": "ṇ",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v", "श": "ś", "ष": "ṣ", "स": "s", "ह": "h",
}
NUKTA_CONSONANTS = {"क़": "q", "ख़": "x", "ग़": "ġ", "ज़": "z", "ड़": "ṛ", "ढ़": "ṛh", "फ़": "f"}
VIRAMA = "्"
NUKTA = "़"
ANUSVARA = "ं"
CANDRABINDU = "ँ"
VISARGA = "ः"
DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
PUNCT = {"।": ".", "॥": ".", "ॐ": "oṃ"}


def _units(word: str) -> list[dict]:
    """Split a word into syllable units: consonant cluster + vowel (+ nasal/visarga)."""
    units: list[dict] = []
    cluster: list[str] = []
    i, n = 0, len(word)
    joined = False  # last consonant was followed by a virama (conjunct continues)

    def close(vowel: str, inherent: bool) -> None:
        units.append({"onset": "".join(cluster), "size": len(cluster), "vowel": vowel, "inherent": inherent, "coda": ""})
        cluster.clear()

    while i < n:
        ch = word[i]
        nxt = word[i + 1] if i + 1 < n else ""
        if ch in CONSONANTS or ch + nxt in NUKTA_CONSONANTS:
            if cluster and not joined:  # previous consonant had no virama → inherent 'a'
                close("a", True)
            joined = False
            if ch + nxt in NUKTA_CONSONANTS:
                cluster.append(NUKTA_CONSONANTS[ch + nxt])
                i += 1
            else:
                cluster.append(CONSONANTS[ch])
            # A following virama keeps the cluster open.
            if i + 1 < n and word[i + 1] == VIRAMA:
                i += 1
                joined = True
                if i + 1 >= n:  # word-final virama: bare consonant
                    close("", False)
                    joined = False
        elif ch in MATRAS:
            close(MATRAS[ch], False)
        elif ch in VOWELS:
            if cluster:
                close("a", True)
            close(VOWELS[ch], False)
        elif ch in (ANUSVARA, CANDRABINDU, VISARGA):
            if cluster:
                close("a", True)
            if units:
                units[-1]["coda"] += {"ं": "ṃ", "ँ": "\u0303", "ः": "ḥ"}[ch]
        elif ch in (NUKTA, VIRAMA):
            pass
        else:
            if cluster:
                close("a", True)
            units.append({"onset": "", "size": 0, "vowel": PUNCT.get(ch, ch), "inherent": False, "coda": ""})
        i += 1
    if cluster:
        close("a", True)
    return units


def _word(word: str) -> str:
    units = _units(word)
    if not units:
        return ""
    last = units[-1]
    # Word-final schwa deletion, except after clusters (इष्ट → iṣṭa), in verb
    # endings in छ (हुन्छ → huncha), in negatives (छैन → chaina, होइन → hoina),
    # and in monosyllables (न, त, र).
    negative = last["onset"] == "n" and len(units) > 1 and units[-2]["vowel"] in ("i", "ai")
    if (
        last["inherent"] and len(units) > 1 and last["size"] == 1 and last["onset"] != "ch"
        and not negative and not units[-2]["coda"].endswith("ḥ")
    ):
        last["vowel"] = ""
    # Medial deletion a → ∅ / VC_CV, scanning right to left, never in adjacent syllables.
    for k in range(len(units) - 2, 0, -1):
        u, prev, nxt = units[k], units[k - 1], units[k + 1]
        if (
            u["inherent"] and not u["coda"] and u["size"] == 1
            and prev["vowel"] and not prev.get("deleted")
            and nxt["vowel"] and nxt["size"] == 1 and not nxt.get("deleted")
        ):
            u["vowel"] = ""
            u["deleted"] = True
    return "".join(u["onset"] + u["vowel"] + u["coda"] for u in units)


def transliterate(text: str) -> str:
    text = text.translate(DIGITS)
    parts = re.split(r"(\s+|[।॥,;:!?\"'‘’“”()\-–—.])", text)
    result = "".join(PUNCT.get(p, _word(p)) if p and p.strip() else p for p in parts)
    result = re.sub(r"\s+([.,;:!?])", r"\1", result)
    # Capitalize sentence starts for readability.
    return re.sub(r"(^[‘“\"']?|[.!?]\s+[‘“\"']?)([a-zāīūṛḍṭṅñṇśṣ])", lambda m: m.group(1) + m.group(2).upper(), result)
