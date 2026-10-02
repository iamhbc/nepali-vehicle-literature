"""Seeding of reference data and import of the processed research corpus."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..knowledge import get_knowledge
from ..models import (
    District,
    Phrase,
    PhraseLabel,
    PhraseTheme,
    Province,
    Reference,
    TaxonomyVersion,
    Theme,
    VehicleType,
)
from ..nlp.normalize import match_key, tokenize
from ..nlp.transliterate import transliterate

log = logging.getLogger(__name__)

# Place names in the corpus that are not district names. Chaurjahari is a
# municipality in Rukum West; मुगाली is the demonym for Mugu.
PLACE_ALIASES = {"मुगाली": "Mugu", "चौरजहारी": "Rukum West"}

LABEL_FIELDS = {
    "emotions": "emotion",
    "love_types": "love",
    "relationship_types": "relationship",
    "rhetorical_devices": "rhetorical",
    "cultural_concepts": "cultural",
}


def _read(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def seed_reference_data(db: Session) -> None:
    s = get_settings()
    kb = get_knowledge()

    if not db.scalar(select(Province.id).limit(1)):
        geo = _read(s.data_dir / "geo" / "nepal_admin.json")
        for prov in geo["provinces"]:
            db.add(Province(id=prov["id"], name_en=prov["name_en"], name_ne=prov["name_ne"]))
            for d in prov["districts"]:
                db.add(District(id=d["id"], province_id=prov["id"], name_en=d["name_en"],
                                name_ne=d["name_ne"], aliases=d.get("aliases", [])))

    existing_vehicles = {v.slug for v in db.scalars(select(VehicleType))}
    for v in _read(s.data_dir / "reference" / "vehicle_types.json")["vehicle_types"]:
        if v["slug"] not in existing_vehicles:
            db.add(VehicleType(**v))

    for t in kb.taxonomy["themes"]:
        theme = db.get(Theme, t["code"]) or Theme(code=t["code"])
        theme.label_en, theme.label_ne = t["label_en"], t["label_ne"]
        theme.group, theme.origin, theme.definition = t["group"], t["origin"], t["definition"]
        db.merge(theme)

    for r in kb.references:
        ref = db.get(Reference, r["id"]) or Reference(id=r["id"])
        for key in ("title", "authors", "year", "source", "url", "kind", "topics"):
            setattr(ref, key, r.get(key))
        ref.note = r.get("note")
        db.merge(ref)

    if not db.scalar(select(TaxonomyVersion).where(TaxonomyVersion.version == kb.version)):
        for tv in db.scalars(select(TaxonomyVersion)):
            tv.is_active = False
        db.add(TaxonomyVersion(version=kb.version, data=kb.taxonomy, is_active=True,
                               note=f"Loaded from {s.taxonomy_path.name}"))
    db.commit()


def places_mentioned(db: Session, text: str) -> list[dict]:
    districts = db.scalars(select(District)).all()
    by_ne = {d.name_ne.split(" ")[0]: d for d in districts}
    by_en = {d.name_en: d for d in districts}
    found: dict[int, dict] = {}
    for tok in tokenize(text):
        for alias, en in PLACE_ALIASES.items():
            if tok.startswith(alias) and en in by_en:
                d = by_en[en]
                found[d.id] = {"district_id": d.id, "district": d.name_en, "surface": tok}
        for name_ne, d in by_ne.items():
            if len(name_ne) > 2 and tok.startswith(name_ne) and len(tok) - len(name_ne) <= 4:
                found[d.id] = {"district_id": d.id, "district": d.name_en, "surface": tok}
    return list(found.values())


def import_corpus(db: Session, path: Path | None = None, force: bool = False) -> dict:
    """Upsert processed corpus records. Records edited by a researcher are skipped unless ``force``."""
    path = path or get_settings().data_dir / "processed" / "corpus.json"
    records = _read(path)
    created = updated = skipped = 0
    for rec in records:
        phrase = db.scalar(select(Phrase).where(Phrase.corpus_id == rec["corpus_id"]))
        if phrase and phrase.updated_by and not force:
            skipped += 1
            continue
        is_new = phrase is None
        if is_new:
            phrase = Phrase(id=rec["id"], corpus_id=rec["corpus_id"])
            db.add(phrase)

        text = rec["text"]
        nepali = text["nepali"] or ""
        candidate = text.get("nepali_candidate")
        searchable = candidate if rec["status"] == "text_missing" and candidate else nepali
        phrase.status = rec["status"]
        phrase.text_nepali = nepali
        phrase.text_candidate = candidate
        phrase.match_key = match_key(searchable)
        phrase.transliteration = text["transliteration"]
        phrase.transliteration_auto = transliterate(searchable) if searchable else None
        phrase.translation = text["translation"]
        phrase.translation_original = text["translation_original"]
        phrase.translation_normalized = text["translation_normalized"]
        phrase.original_theme = rec["original_theme"]
        phrase.coding = rec["coding"]
        phrase.needs_review = rec["review"]["needs_review"]
        phrase.review_reason = rec["review"]["reason"]
        phrase.review_priority = rec["review"]["priority"]
        phrase.qc_flags = rec["qc_flags"]
        phrase.clusters = rec["clusters"]
        phrase.variant_group = (rec.get("variant") or {}).get("group")
        phrase.variant_relation = (rec.get("variant") or {}).get("relation")
        phrase.provenance = rec["provenance"]
        phrase.source = "research-corpus"
        phrase.places_mentioned = places_mentioned(db, searchable)

        # Replace child rows: delete old ones first so unique constraints hold.
        if not is_new:
            phrase.themes.clear()
            phrase.labels.clear()
            db.flush()
        # Corpus codes are an AI first pass (see codebook): imported as "proposed".
        phrase.themes = [
            PhraseTheme(theme_code=code, source="corpus", status="proposed",
                        confidence=rec["coding"].get("confidence"))
            for code in rec["codes"]
        ]
        labels = []
        coding = rec["coding"]
        for field_name, dimension in LABEL_FIELDS.items():
            for label in coding.get(field_name) or []:
                labels.append(PhraseLabel(dimension=dimension, label=label[:160], source="corpus",
                                          status="proposed", confidence=coding.get("confidence"),
                                          evidence=coding.get("evidence") or []))
        for stance in (coding.get("power_hierarchy") or {}).get("stances", []):
            labels.append(PhraseLabel(dimension="power_stance", label=stance, source="corpus",
                                      status="proposed", confidence=coding.get("confidence"),
                                      explanation=(coding.get("power_hierarchy") or {}).get("note")))
        phrase.labels = labels
        created += is_new
        updated += not is_new
    db.commit()
    result = {"created": created, "updated": updated, "skipped_researcher_edited": skipped, "source": str(path)}
    log.info("Corpus import: %s", result)
    return result
