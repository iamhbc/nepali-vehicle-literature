#!/usr/bin/env python3
"""Transform the original research workbook into a normalized, versioned corpus.

The original file in ``data/raw/`` is opened read-only and never modified.
Output goes to ``data/processed/``:

* ``corpus.json``    — one structured record per inscription
* ``codebook.json``  — theme codes with definitions and origin
* ``clusters.json``  — emergent clusters with member ids
* ``manifest.json``  — provenance (source checksum, counts, processing notes)

Usage::

    python scripts/process_corpus.py [path/to/workbook.xlsx]
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "raw" / "Vehicle_Inscriptions_Master_Dataset.xlsx"
OUT_DIR = ROOT / "data" / "processed"

# Values the coders used to mean "no textual basis". Not a negative finding.
EMPTY_TOKENS = {"", "—", "-", "–", "n/a", "na", "not evident", "none", "<none>"}

POWER_STANCES = ["Reproduction", "Reflection", "Critique", "Resistance", "Ambiguous"]

MULTI_LABEL_FIELDS = {
    "Text_Type": "text_types",
    "Secondary_Domains": "secondary_domains",
    "Emotion": "emotions",
    "Emotional_Target": "emotional_targets",
    "Relationship_Type": "relationship_types",
    "Love_Type": "love_types",
    "Cultural_Concepts": "cultural_concepts",
    "Rhetorical_Device": "rhetorical_devices",
}

SINGLE_FIELDS = {
    "Primary_Domain": "primary_domain",
    "Emotion_Intensity": "emotion_intensity",
    "Economic_Theme": "economic_theme",
    "Political_Theme": "political_theme",
    "Religious_Theme": "religious_theme",
    "Gender_Theme": "gender_theme",
    "Identity_Theme": "identity_theme",
    "Aspiration": "aspiration",
    "Agency": "agency",
    "Humor_Irony": "humor_irony",
    "Valence": "valence",
    "Temporal_Orientation": "temporal_orientation",
    "Deeper_Meaning": "deeper_meaning",
    "Confidence": "confidence",
    "Alternative_Interpretation": "alternative_interpretation",
}


def clean(value) -> str | None:
    if value is None:
        return None
    text = unicodedata.normalize("NFC", str(value)).strip()
    text = re.sub(r"\\([\-!*_.])", r"\1", text)  # stray markdown escapes
    return None if text.lower() in EMPTY_TOKENS else text


def split_multi(value) -> list[str]:
    text = clean(value)
    if not text:
        return []
    return [part for part in (clean(p) for p in text.split("|")) if part]


def split_theme(value) -> list[str]:
    """The original theme column mixes commas and semicolons (see QC log)."""
    text = clean(value)
    if not text:
        return []
    parts = re.split(r"[;,]", text.rstrip("."))
    return [p.strip().rstrip(".") for p in parts if p.strip()]


def parse_power(value) -> dict:
    text = clean(value)
    if not text:
        return {"stances": [], "note": None}
    # Keep the coder's order ("Critique + Reproduction" leads with Critique).
    low = text.lower()
    stances = sorted((s for s in POWER_STANCES if s.lower() in low), key=lambda s: low.index(s.lower()))
    note = None
    match = re.search(r"\((.+)\)", text)
    if match:
        note = match.group(1)
    return {"stances": stances, "note": note, "raw": text}


def parse_id_list(text: str) -> list[int]:
    ids: list[int] = []
    for token in re.split(r"[,\s/]+", str(text)):
        if token.isdigit():
            ids.append(int(token))
    return ids


def sheet_rows(wb, name: str) -> list[tuple]:
    return list(wb[name].iter_rows(values_only=True))


# Candidate Devanagari for rows whose Nepali cell is unusable, reconstructed from
# the surviving transliteration. Never written into the original field; flagged
# for verification against the source photograph.
RECONSTRUCTIONS = {
    52: "आमाको फाटेको चोला मात्र नहेर, बुबाको फुटेको कुर्कुच्चा पनि हेर्ने गर। "
        "दुःख पर्दा आमाको त जाने माइती हुन्छ; तर बुबाको पीडा कहाँ गएर सुनाउने?",
}


def fix_transliteration(text: str | None) -> tuple[str | None, list[str]]:
    """Apply the corrections documented in the QC log, keeping a note of each."""
    if not text:
        return text, []
    notes = []
    fixed = text
    if "pardcha" in fixed:
        fixed = fixed.replace("pardcha", "parcha")
        notes.append("'-pardcha' corrected to '-parcha' (QC log)")
    return fixed, notes


def main(source: Path) -> None:
    raw_bytes = source.read_bytes()
    checksum = hashlib.sha256(raw_bytes).hexdigest()
    wb = openpyxl.load_workbook(source, read_only=True, data_only=True)

    master = sheet_rows(wb, "Master_Dataset")
    header = [h for h in master[0]]
    col = {name: idx for idx, name in enumerate(header)}

    # --- Codebook ---------------------------------------------------------
    codebook = []
    for row in sheet_rows(wb, "Codebook"):
        if row and row[0] and re.fullmatch(r"[A-Z_]+", str(row[0])) and row[1] in ("Deductive", "Emergent"):
            codebook.append({"code": row[0], "origin": row[1], "definition": clean(row[2])})
    codebook_notes = [clean(r[0]) for r in sheet_rows(wb, "Codebook")[2:10] if r and clean(r[0])]

    # --- Clusters ---------------------------------------------------------
    clusters = []
    for row in sheet_rows(wb, "Clusters")[1:]:
        if not row or not row[0]:
            continue
        clusters.append({
            "name": clean(row[0]),
            "member_ids": parse_id_list(row[1]),
            "description": clean(row[2]),
        })

    # --- Human review queue ----------------------------------------------
    review_priority: dict[int, str] = {}
    for row in sheet_rows(wb, "Human_Review")[1:]:
        if row and isinstance(row[0], (int, float)):
            review_priority[int(row[0])] = clean(row[2]) or "Medium"

    # --- QC log -----------------------------------------------------------
    qc_by_id: dict[int, list[dict]] = {}
    qc_global: list[dict] = []
    for row in sheet_rows(wb, "QC_Log")[1:]:
        if not row or not row[0]:
            continue
        entry = {"check": clean(row[0]), "finding": clean(row[1])}
        ids = parse_id_list(row[2]) if row[2] and str(row[2]).strip() not in ("—", "All") else []
        if not ids:
            entry["scope"] = clean(row[2]) or "—"
            qc_global.append(entry)
        for i in ids:
            qc_by_id.setdefault(i, []).append(entry)

    # Variant groups documented in the QC log.
    variant_groups = {
        9: ("dup-9-47", "near-duplicate (होइन/हैन)"),
        47: ("dup-9-47", "near-duplicate (होइन/हैन)"),
        20: ("tpl-fare-love", "template variant (fare-and-love)"),
        23: ("tpl-fare-love", "template variant (fare-and-love)"),
        14: ("rhyme-katar-hatar", "shared rhyme formula (कतार/हतार)"),
        54: ("rhyme-katar-hatar", "shared rhyme formula (कतार/हतार)"),
    }

    records = []
    for excel_row, row in enumerate(master[1:], start=2):
        if row[col["ID"]] is None:
            continue
        pid = int(row[col["ID"]])
        nepali = clean(row[col["Original_Nepali"]])
        status = "active"
        if not nepali or not re.search(r"[\u0900-\u097F]", nepali):
            status = "text_missing"

        translit_original = clean(row[col["Transliteration"]])
        translit, translit_notes = fix_transliteration(translit_original)
        t_original = clean(row[col["Original_Translation"]])
        t_normalized = clean(row[col["Normalized_Translation"]])

        coding: dict = {}
        for src, dst in MULTI_LABEL_FIELDS.items():
            coding[dst] = split_multi(row[col[src]])
        for src, dst in SINGLE_FIELDS.items():
            coding[dst] = clean(row[col[src]])
        coding["power_hierarchy"] = parse_power(row[col["Power_Hierarchy"]])
        evidence = clean(row[col["Evidence"]])
        coding["evidence"] = [e.strip() for e in evidence.split(" / ")] if evidence else []

        needs_review = (clean(row[col["Human_Review"]]) or "").upper() == "Y"
        variant = variant_groups.get(pid)

        records.append({
            "id": pid,
            "corpus_id": f"NVL-{pid:03d}",
            "status": status,
            "text": {
                "nepali": nepali,
                "nepali_candidate": RECONSTRUCTIONS.get(pid) if status == "text_missing" else None,
                "nepali_candidate_note": (
                    "Reconstructed from the transliteration; verify against the source photograph."
                    if status == "text_missing" and pid in RECONSTRUCTIONS else None
                ),
                "transliteration": translit,
                "transliteration_original": translit_original,
                "transliteration_notes": translit_notes,
                "translation": t_normalized or t_original,
                "translation_original": t_original,
                "translation_normalized": t_normalized,
            },
            "original_theme": split_theme(row[col["Original_Theme"]]),
            "coding": coding,
            "codes": split_multi(row[col["Codes"]]),
            "review": {
                "needs_review": needs_review,
                "reason": clean(row[col["Review_Reason"]]),
                "priority": review_priority.get(pid) if needs_review else None,
                "coder": "AI first pass (Claude); not yet validated by a native speaker",
            },
            "qc_flags": qc_by_id.get(pid, []),
            "clusters": [c["name"] for c in clusters if pid in c["member_ids"]],
            "variant": {"group": variant[0], "relation": variant[1]} if variant else None,
            # The source has no observation context for any row (QC log).
            "context": {"vehicle_type": None, "location": None, "observed_at": None, "photo_ref": None},
            "provenance": {
                "source_file": source.name,
                "sheet": "Master_Dataset",
                "row": excel_row,
                "sha256": checksum,
            },
        })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dump = lambda name, data: (OUT_DIR / name).write_text(  # noqa: E731
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    dump("corpus.json", records)
    dump("codebook.json", {"notes": codebook_notes, "codes": codebook})
    dump("clusters.json", clusters)
    dump("manifest.json", {
        "source_file": f"data/raw/{source.name}",
        "source_sha256": checksum,
        "processed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "processor": "scripts/process_corpus.py",
        "counts": {
            "records": len(records),
            "active": sum(r["status"] == "active" for r in records),
            "text_missing": sum(r["status"] == "text_missing" for r in records),
            "needs_review": sum(r["review"]["needs_review"] for r in records),
            "codes": len(codebook),
            "clusters": len(clusters),
        },
        "global_qc_findings": qc_global,
        "notes": [
            "Original fields are preserved verbatim; corrections live in separate *_normalized fields.",
            "Multi-label fields are split on '|'. Empty markers ('Not evident', 'N/A', '—') become null/[].",
            "Power_Hierarchy is parsed into stances (Reproduction/Reflection/Critique/Resistance/Ambiguous) with the coder's note kept.",
        ],
    })
    print(f"Wrote {len(records)} records, {len(codebook)} codes, {len(clusters)} clusters to {OUT_DIR}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE)
