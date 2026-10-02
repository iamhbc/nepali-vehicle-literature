"""Deterministic detectors for rhetorical form in Nepali couplets and sayings."""

from __future__ import annotations

import re

from ..nlp.normalize import match_key, tokenize
from .schema import Finding

# Case endings (in match-key spelling) that make words look rhymed without a sound rhyme.
CASE_SUFFIXES = ("लाई", "लाइ", "हरु", "को", "का", "कि", "मा", "ले", "बाट", "सँग", "संग")
INTERROGATIVES = {"के", "किन", "कहाँ", "कसरी", "कति", "कसले", "कसको", "कता", "केको", "कुन", "को", "कसलाई", "कहिले"}
ANTONYMS = [
    ("धनी", "गरिब"), ("सुख", "दुःख"), ("स्त्री", "पुरुष"), ("मर्द", "नामर्द"), ("झुट", "सत्य"),
    ("झुट", "साँचो"), ("राम्रो", "नराम्रो"), ("हुँदा", "नहुँदा"), ("जन्म", "मृत्यु"), ("हाँसो", "आँसु"),
    ("अँध्यारा", "बिहानी"), ("रात", "बिहानी"), ("पहिले", "अहिले"), ("जोड्छन्", "छोड्छन्"),
]


def _clauses(text: str) -> list[str]:
    parts = re.split(r"[;।?!\n]|,(?=\s)", text)
    return [p.strip(" \"'“”‘’") for p in parts if len(tokenize(p)) >= 2]


def detect(text: str) -> list[Finding]:
    findings: list[Finding] = []
    clauses = _clauses(text)
    tokens = tokenize(text)

    # Rhyme / epistrophe between clause-final words. When the final word is a
    # short repeated refrain (रदिफ, e.g. "छ", "रे"), the rhyme (काफिया) falls on
    # the word before it — the ghazal pattern common in painted couplets.
    tails = [tokenize(c) for c in clauses]
    rhymes: list[tuple[str, str]] = []
    parallels: list[tuple[str, str]] = []
    refrains: dict[str, int] = {}
    repeats: dict[str, int] = {}
    for i in range(len(tails)):
        for j in range(i + 1, len(tails)):
            a, b = tails[i][-1], tails[j][-1]
            ka, kb_ = match_key(a), match_key(b)
            if ka == kb_:
                if len(ka) <= 3 and len(tails[i]) > 1 and len(tails[j]) > 1:
                    refrains[a] = refrains.get(a, 1) + 1
                    a, b = tails[i][-2], tails[j][-2]
                    ka, kb_ = match_key(a), match_key(b)
                else:
                    repeats[a] = repeats.get(a, 1) + 1
                    continue
            if ka != kb_ and len(ka) >= 2 and len(kb_) >= 2 and ka[-2:] == kb_[-2:]:
                suffix = next((x for x in CASE_SUFFIXES if ka.endswith(x) and kb_.endswith(x)), None)
                if suffix:
                    sa, sb = ka[: -len(suffix)], kb_[: -len(suffix)]
                    if not (len(sa) >= 2 and len(sb) >= 2 and sa[-2:] == sb[-2:]):
                        if (a, b) not in parallels:
                            parallels.append((a, b))
                        continue
                if (a, b) not in rhymes:
                    rhymes.append((a, b))
    if rhymes:
        pairs = rhymes[:3]
        refrain_note = (
            f" before the repeated refrain «{next(iter(refrains))}» (the रदिफ–काफिया pattern of the Nepali ghazal)"
            if refrains else ""
        )
        findings.append(Finding(
            label="Rhyme",
            explanation="Clause-final words share their closing sounds ("
            + "; ".join(f"{a} / {b}" for a, b in pairs)
            + ")" + refrain_note + ", a typical device of painted couplets that makes the line memorable.",
            evidence=sorted({w for pair in pairs for w in pair}),
            confidence="high", kind="evidence",
        ))
    if parallels:
        findings.append(Finding(
            label="Parallelism",
            explanation="Clauses end in the same grammatical form ("
            + "; ".join(f"{a} / {b}" for a, b in parallels[:3])
            + "), building a list-like, proverbial rhythm rather than a sound rhyme.",
            evidence=sorted({w for pair in parallels[:3] for w in pair}),
            confidence="high", kind="evidence",
        ))
    for word, count in repeats.items():
        findings.append(Finding(
            label="Repetition",
            explanation=f"The clause ending «{word}» recurs {count} times (epistrophe), building emphasis.",
            evidence=[word], confidence="high", kind="evidence",
        ))

    # Anaphora: clauses opening with the same word.
    openers: dict[str, int] = {}
    for c in clauses:
        first = tokenize(c)[0]
        openers[first] = openers.get(first, 0) + 1
    for word, count in openers.items():
        if count >= 2 and len(word) > 1:
            findings.append(Finding(
                label="Anaphora",
                explanation=f"{count} clauses open with «{word}», giving the saying a parallel, list-like rhythm.",
                evidence=[word], confidence="high", kind="evidence",
            ))

    # Antithesis by negation (X / नX) and by lexical opposites.
    keys = {match_key(t): t for t in tokens}
    negated = [(keys[k[1:]], keys[k]) for k in keys if k.startswith("न") and len(k) > 3 and k[1:] in keys]
    opposites = [(a, b) for a, b in ANTONYMS
                 if any(match_key(t).startswith(match_key(a)) for t in tokens)
                 and any(match_key(t).startswith(match_key(b)) for t in tokens)]
    if negated or opposites:
        pairs = [f"{a} / {b}" for a, b in (negated + opposites)[:3]]
        evidence = [w for a, b in negated[:3] for w in (a, b)] or [
            t for a, b in opposites[:2] for t in tokens if match_key(t).startswith(match_key(a)) or match_key(t).startswith(match_key(b))
        ]
        findings.append(Finding(
            label="Antithesis",
            explanation="The saying sets opposites against each other (" + "; ".join(pairs)
            + "), a structure that frames a dilemma or contrast.",
            evidence=sorted(set(evidence))[:6], confidence="high" if negated else "medium", kind="evidence",
        ))

    # Rhetorical questions.
    questions = [re.split(r"[;।,]", q)[-1] for q in re.split(r"(?<=[?])", text) if "?" in q]
    asked = [q.strip() for q in questions if q.strip()] or [c for c in clauses if tokenize(c)[0] in INTERROGATIVES]
    if asked:
        findings.append(Finding(
            label="Rhetorical question",
            explanation="The phrase poses a question that seems to expect no literal answer; such questions usually carry complaint, irony or challenge.",
            evidence=[asked[0].rstrip("?").strip()[:80] or asked[0]], confidence="medium", kind="interpretation",
        ))

    # Code-mixing (Latin script inside Devanagari text).
    latin = re.findall(r"[A-Za-z]{2,}", text)
    if latin and re.search(r"[ऀ-ॿ]", text):
        findings.append(Finding(
            label="Code-mixing",
            explanation="English words in Latin script sit inside the Nepali line, a marker of youth and urban registers.",
            evidence=latin[:4], confidence="high", kind="evidence",
        ))

    # Reported speech (quotation or the hearsay particle रे / अरे).
    quoted = re.findall(r"[\"“‘']([^\"”’']{2,})[\"”’']", text)
    hearsay = [t for t in tokens if t in ("रे", "अरे")]
    if quoted or hearsay:
        findings.append(Finding(
            label="Reported speech",
            explanation="The line quotes or reports someone else's words (quotation marks or the hearsay particle रे), often to ironise them.",
            evidence=(quoted[:2] or hearsay[:1]), confidence="high", kind="evidence",
        ))
    return findings
