"""Evidence verification and confidence calibration.

Runs after every engine. It never adds claims; it only removes unverifiable
quotes and lowers confidence, so a model cannot cite words that are not on the
vehicle.
"""

from __future__ import annotations

from ..knowledge import get_knowledge
from ..nlp.normalize import match_key
from .schema import AnalysisPayload, Finding, Verification, VerificationIssue

_DOWN = {"high": "medium", "medium": "low", "low": "low"}
_SENSITIVE_STEMS = ("misogyn", "misandr", "patriarch", "objectif", "caste", "ethnic", "party", "partisan", "religious identity")


def _dimension_findings(p: AnalysisPayload) -> list[tuple[str, list[Finding]]]:
    return [
        ("emotion", p.emotion.findings),
        ("love", p.love.findings),
        ("relationship", p.relationships.findings),
        ("social", p.social.findings),
        ("economic", p.economic.findings),
        ("political", p.political.findings),
        ("gender_power", p.gender_power.findings),
        ("cultural", p.cultural.findings),
        ("philosophical", p.philosophical.findings),
        ("rhetoric", p.rhetoric.findings),
    ]


def quote_in_text(quote: str, text: str, text_key: str | None = None) -> bool:
    if not quote.strip():
        return False
    if quote in text:
        return True
    qk = match_key(quote)
    return bool(qk) and qk in (text_key if text_key is not None else match_key(text))


def is_sensitive(label: str) -> bool:
    low = label.lower()
    sensitive = {s.lower() for s in get_knowledge().taxonomy.get("sensitive_labels", [])}
    return low in sensitive or any(stem in low for stem in _SENSITIVE_STEMS)


def verify(payload: AnalysisPayload, text: str) -> tuple[AnalysisPayload, Verification, list[str]]:
    kb = get_knowledge()
    text_key = match_key(text)
    issues: list[VerificationIssue] = []
    warnings: list[str] = []
    checked = quotes = verified = 0

    for dimension, findings in _dimension_findings(payload):
        for f in findings:
            checked += 1
            kept = []
            for q in f.evidence:
                quotes += 1
                if quote_in_text(q, text, text_key):
                    verified += 1
                    kept.append(q)
                else:
                    issues.append(VerificationIssue(dimension=dimension, label=f.label, quote=q,
                                                    action="quote not found in the phrase; removed and confidence lowered"))
                    f.confidence = _DOWN[f.confidence]
            f.evidence = kept
            if not kept and f.kind == "evidence":
                f.kind = "interpretation"
            if is_sensitive(f.label) and not kept and (f.kind != "hypothesis" or f.confidence != "low"):
                f.kind, f.confidence = "hypothesis", "low"
                issues.append(VerificationIssue(dimension=dimension, label=f.label, quote="",
                                                action="sensitive label without verified evidence; marked as low-confidence hypothesis"))

    known = []
    for t in payload.themes:
        if t.code in kb.themes:
            known.append(t)
        else:
            warnings.append(f"Ignored unknown theme code '{t.code}'.")
    payload.themes = known

    if quotes and verified < quotes:
        warnings.append(f"{quotes - verified} of {quotes} evidence quotes could not be found in the phrase and were removed.")
    if payload.overall_confidence == "high" and (issues or payload.ambiguity.is_ambiguous):
        payload.overall_confidence = "medium"
    return payload, Verification(findings_checked=checked, quotes_checked=quotes, quotes_verified=verified, issues=issues), warnings
