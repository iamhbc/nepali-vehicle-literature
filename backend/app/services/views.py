"""Read models for corpus browsing, phrase detail and research statistics."""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..analysis import baseline
from ..analysis.graph import build_graph
from ..analysis.schema import RelatedEntry
from ..knowledge import get_knowledge
from ..models import Analysis, District, Phrase, Province, Submission, VehicleType
from ..retrieval.search import get_corpus_index

PRIORITY_ORDER = {"High — meaning changes": 0, "Medium": 1, "Low": 2}


def active_codes(p: Phrase) -> list[str]:
    return [t.theme_code for t in p.themes if t.status != "rejected"]


def phrase_summary(p: Phrase) -> dict:
    coding = p.coding or {}
    return {
        "id": p.id,
        "corpus_id": p.corpus_id,
        "status": p.status,
        "text": p.searchable_text,
        "text_is_candidate": p.status == "text_missing" and bool(p.text_candidate),
        "transliteration": p.transliteration or p.transliteration_auto,
        "translation": p.translation,
        "codes": active_codes(p),
        "valence": coding.get("valence"),
        "emotions": coding.get("emotions") or [],
        "text_types": coding.get("text_types") or [],
        "confidence": coding.get("confidence"),
        "needs_review": p.needs_review,
        "review_priority": p.review_priority,
        "clusters": p.clusters or [],
        "variant_group": p.variant_group,
        "vehicle_type": p.vehicle_type.slug if p.vehicle_type else None,
        "district": p.district.name_en if p.district else None,
        "places_mentioned": p.places_mentioned or [],
        "source": p.source,
    }


def list_phrases(db: Session, theme: str | None = None, cluster: str | None = None, valence: str | None = None,
                 needs_review: bool | None = None, include_archived: bool = False) -> list[Phrase]:
    stmt = select(Phrase).options(selectinload(Phrase.themes), selectinload(Phrase.vehicle_type), selectinload(Phrase.district))
    if not include_archived:
        stmt = stmt.where(Phrase.status != "archived")
    if needs_review is not None:
        stmt = stmt.where(Phrase.needs_review == needs_review)
    phrases = db.scalars(stmt.order_by(Phrase.id)).all()
    out = []
    for p in phrases:
        if theme and theme not in active_codes(p):
            continue
        if cluster and cluster not in (p.clusters or []):
            continue
        if valence and (p.coding or {}).get("valence", "").lower() != valence.lower():
            continue
        out.append(p)
    return out


def phrase_detail(db: Session, p: Phrase) -> dict:
    kb = get_knowledge()
    index = get_corpus_index()
    codes = active_codes(p)
    meta = index.meta.get(p.id)
    payload = baseline.from_corpus(p.searchable_text, meta, p.coding or {}, kb) if meta else None
    related = [
        RelatedEntry(id=h.id, corpus_id=h.meta.corpus_id, text=h.meta.text, translation=h.meta.translation, score=h.score,
                     reasons=h.reasons, codes=h.meta.codes, needs_review=h.meta.needs_review, status=h.meta.status)
        for h in index.related(p.searchable_text, k=6, codes=codes, exclude={p.id})
    ]
    concepts = []
    for hit in kb.match_concepts(p.searchable_text):
        c = kb.concepts_by_slug[hit.slug]
        concepts.append({**c, "surface": hit.token})
    graph = build_graph(p.searchable_text, payload, related, concepts) if payload else None
    variants = []
    if p.variant_group:
        variants = [
            {"id": v.id, "corpus_id": v.corpus_id, "text": v.searchable_text, "relation": v.variant_relation}
            for v in db.scalars(select(Phrase).where(Phrase.variant_group == p.variant_group, Phrase.id != p.id))
        ]
    return {
        **phrase_summary(p),
        "text_original": p.text_nepali,
        "text_candidate": p.text_candidate,
        "transliteration_original": p.transliteration,
        "transliteration_auto": p.transliteration_auto,
        "translation_original": p.translation_original,
        "translation_normalized": p.translation_normalized,
        "original_theme": p.original_theme,
        "coding": p.coding,
        "themes": [{"code": t.theme_code, "source": t.source, "status": t.status, "confidence": t.confidence,
                    "rationale": t.rationale, "label_en": kb.themes.get(t.theme_code, {}).get("label_en")} for t in p.themes],
        "labels": [{"id": l.id, "dimension": l.dimension, "label": l.label, "source": l.source, "status": l.status,
                    "confidence": l.confidence} for l in p.labels],
        "review_reason": p.review_reason,
        "qc_flags": p.qc_flags,
        "variants": variants,
        "provenance": p.provenance,
        "related": [r.model_dump() for r in related],
        "concepts": concepts,
        "graph": graph.model_dump() if graph else None,
        "updated_by": p.updated_by,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def corpus_stats(db: Session) -> dict:
    kb = get_knowledge()
    phrases = list_phrases(db)
    n = len(phrases)
    theme_counts = Counter(c for p in phrases for c in active_codes(p))
    families = Counter()
    raw_emotions = Counter()
    for p in phrases:
        fams = {kb.emotion_family(e) or "other" for e in (p.coding or {}).get("emotions") or []}
        families.update(fams)
        raw_emotions.update((p.coding or {}).get("emotions") or [])
    valence = Counter(((p.coding or {}).get("valence") or "Uncoded") for p in phrases)
    love = Counter(baseline._love_key(l) for p in phrases for l in (p.coding or {}).get("love_types") or [])
    stances = Counter(s for p in phrases for s in ((p.coding or {}).get("power_hierarchy") or {}).get("stances", []))
    text_types = Counter(t for p in phrases for t in (p.coding or {}).get("text_types") or [])

    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    for p in phrases:
        for a, b in combinations(sorted(set(active_codes(p))), 2):
            pair_counts[(a, b)] += 1
    cooccurrence = [{"source": a, "target": b, "count": c} for (a, b), c in sorted(pair_counts.items(), key=lambda kv: -kv[1])]

    clusters = Counter(c for p in phrases for c in p.clusters or [])
    vehicles = Counter(p.vehicle_type.slug for p in phrases if p.vehicle_type)
    observed = Counter(p.district.name_en for p in phrases if p.district)
    mentioned = Counter(m["district"] for p in phrases for m in p.places_mentioned or [])
    provinces = {d.name_en: prov.name_en for prov in db.scalars(select(Province)) for d in prov.districts}

    themes_meta = {t["code"]: t for t in kb.taxonomy["themes"]}
    return {
        "total": n,
        "needs_review": sum(p.needs_review for p in phrases),
        "text_missing": sum(p.status == "text_missing" for p in phrases),
        "analyses_run": db.scalar(select(func.count(Analysis.id))) or 0,
        "submissions_pending": db.scalar(select(func.count(Submission.id)).where(Submission.status == "pending")) or 0,
        "themes": [{"code": c, "label_en": themes_meta[c]["label_en"], "label_ne": themes_meta[c]["label_ne"],
                    "group": themes_meta[c]["group"], "count": theme_counts.get(c, 0)} for c in themes_meta],
        "emotion_families": [{"key": k, "label_en": kb.emotion_families.get(k, {}).get("label_en", k.title()),
                              "label_ne": kb.emotion_families.get(k, {}).get("label_ne"), "count": v}
                             for k, v in families.most_common()],
        "emotions": [{"label": k, "count": v} for k, v in raw_emotions.most_common(25)],
        "valence": [{"label": k, "count": v} for k, v in valence.most_common()],
        "love_types": [{"key": k, "label_en": kb.love_types.get(k, {}).get("label_en", k), "count": v} for k, v in love.most_common()],
        "power_stances": [{"label": k, "count": v} for k, v in stances.most_common()],
        "text_types": [{"label": k, "count": v} for k, v in text_types.most_common(15)],
        "cooccurrence": cooccurrence,
        "clusters": [{"name": k, "count": v} for k, v in clusters.most_common()],
        "vehicles": [{"slug": k, "count": v} for k, v in vehicles.most_common()],
        "geography": {
            "observed": [{"district": k, "province": provinces.get(k), "count": v} for k, v in observed.most_common()],
            "mentioned": [{"district": k, "province": provinces.get(k), "count": v} for k, v in mentioned.most_common()],
        },
    }


def location_tree(db: Session) -> list[dict]:
    provinces = db.scalars(select(Province).options(selectinload(Province.districts)).order_by(Province.id)).all()
    return [{"id": p.id, "name_en": p.name_en, "name_ne": p.name_ne,
             "districts": [{"id": d.id, "name_en": d.name_en, "name_ne": d.name_ne, "aliases": d.aliases} for d in p.districts]}
            for p in provinces]


def vehicle_list(db: Session) -> list[dict]:
    return [{"id": v.id, "slug": v.slug, "name_en": v.name_en, "name_ne": v.name_ne}
            for v in db.scalars(select(VehicleType).order_by(VehicleType.id))]


def example_phrases(db: Session, k: int = 8) -> list[dict]:
    """Diverse, high-confidence corpus entries that do not need meaning-changing corrections."""
    picked, seen_groups, seen_variants = [], set(), set()
    for p in list_phrases(db):
        coding = p.coding or {}
        if p.status != "active" or coding.get("confidence") != "High":
            continue
        if p.review_priority and p.review_priority.startswith("High"):
            continue
        if p.variant_group and p.variant_group in seen_variants:
            continue
        group = (active_codes(p) or ["?"])[0]
        if group in seen_groups or len(p.searchable_text) > 110:
            continue
        seen_groups.add(group)
        if p.variant_group:
            seen_variants.add(p.variant_group)
        picked.append(phrase_summary(p))
        if len(picked) >= k:
            break
    return picked


def district_by_id(db: Session, district_id: int | None) -> District | None:
    return db.get(District, district_id) if district_id else None
