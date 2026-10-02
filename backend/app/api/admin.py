"""Protected researcher API: corpus management, human-in-the-loop review, exports, analytics."""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..analysis import prompts
from ..analysis.engine import AnalysisInputError, get_engine
from ..auth import create_token, login_guard, require_admin, verify_credentials
from ..db import get_db
from ..knowledge import get_knowledge
from ..models import (
    Analysis,
    Phrase,
    PhraseTheme,
    Reference,
    ReviewEvent,
    Submission,
    TaxonomyVersion,
    Theme,
    VehicleType,
)
from ..nlp.normalize import match_key, normalize_text
from ..nlp.transliterate import transliterate
from ..retrieval.search import get_corpus_index
from ..services import views
from ..services.corpus import import_corpus, places_mentioned
from ..services.geo import import_municipalities

router = APIRouter(prefix="/api/admin", tags=["admin"])
auth_router = APIRouter(prefix="/api/admin", tags=["admin"])


def _audit(db: Session, reviewer: str, target_type: str, target_id, action: str, before=None, after=None, note=None) -> None:
    db.add(ReviewEvent(target_type=target_type, target_id=str(target_id), action=action, before=before, after=after,
                       reviewer=reviewer, note=note))


def _snapshot(p: Phrase) -> dict:
    return {"text": p.text_nepali, "translation_normalized": p.translation_normalized, "status": p.status,
            "needs_review": p.needs_review, "coding": p.coding, "codes": views.active_codes(p)}


def _get_phrase(db: Session, phrase_id: int) -> Phrase:
    p = db.get(Phrase, phrase_id)
    if not p:
        raise HTTPException(404, "Corpus entry not found.")
    return p


def _next_corpus_id(db: Session) -> tuple[int, str]:
    max_id = db.scalar(select(func.max(Phrase.id))) or 0
    return max_id + 1, f"NVL-{max_id + 1:03d}"


# --- Auth ------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


@auth_router.post("/login")
def login(req: LoginRequest, request: Request) -> dict:
    login_guard(request)
    if not verify_credentials(req.username, req.password):
        raise HTTPException(401, "Incorrect username or password.")
    token, expires = create_token(req.username)
    return {"token": token, "expires_at": expires.isoformat(), "username": req.username}


@router.get("/me")
def me(user: str = Depends(require_admin)) -> dict:
    return {"username": user}


# --- Review queue & phrases ----------------------------------------------------------------


@router.get("/review-queue")
def review_queue(db: Session = Depends(get_db), _: str = Depends(require_admin)) -> list[dict]:
    rows = views.list_phrases(db, needs_review=True)
    rows.sort(key=lambda p: (views.PRIORITY_ORDER.get(p.review_priority or "", 3), p.id))
    return [{**views.phrase_summary(p), "review_reason": p.review_reason, "qc_flags": p.qc_flags} for p in rows]


@router.get("/phrases")
def all_phrases(db: Session = Depends(get_db), _: str = Depends(require_admin),
                include_archived: bool = True) -> list[dict]:
    return [views.phrase_summary(p) for p in views.list_phrases(db, include_archived=include_archived)]


@router.get("/phrases/{phrase_id}")
def phrase_detail(phrase_id: int, db: Session = Depends(get_db), _: str = Depends(require_admin)) -> dict:
    return views.phrase_detail(db, _get_phrase(db, phrase_id))


class PhraseIn(BaseModel):
    text_nepali: str = Field(..., min_length=1, max_length=2000)
    transliteration: str | None = None
    translation: str | None = None
    coding: dict | None = None
    codes: list[str] = []
    vehicle_type: str | None = None
    province_id: int | None = None
    district_id: int | None = None
    municipality_id: int | None = None
    locality: str | None = None
    source: str = "researcher"
    note: str | None = None


class PhraseUpdate(BaseModel):
    text_nepali: str | None = Field(None, max_length=2000)
    transliteration: str | None = None
    translation_normalized: str | None = None
    coding: dict | None = None
    needs_review: bool | None = None
    review_reason: str | None = None
    status: Literal["active", "text_missing", "archived"] | None = None
    vehicle_type: str | None = None
    province_id: int | None = None
    district_id: int | None = None
    municipality_id: int | None = None
    locality: str | None = None
    note: str | None = None


def _apply_context(db: Session, p: Phrase, data: dict) -> None:
    if "vehicle_type" in data:
        v = db.scalar(select(VehicleType).where(VehicleType.slug == data["vehicle_type"])) if data["vehicle_type"] else None
        p.vehicle_type_id = v.id if v else None
    for key in ("province_id", "district_id", "municipality_id", "locality"):
        if key in data:
            setattr(p, key, data[key])


@router.post("/phrases", status_code=201)
def create_phrase(req: PhraseIn, db: Session = Depends(get_db), user: str = Depends(require_admin)) -> dict:
    kb = get_knowledge()
    text = normalize_text(req.text_nepali)
    pid, corpus_id = _next_corpus_id(db)
    p = Phrase(id=pid, corpus_id=corpus_id, status="active", text_nepali=text, match_key=match_key(text),
               transliteration=req.transliteration, transliteration_auto=transliterate(text),
               translation=req.translation, translation_normalized=req.translation, coding=req.coding or {},
               source=req.source, needs_review=True, review_reason="New entry; awaiting coding review.",
               updated_by=user, places_mentioned=places_mentioned(db, text),
               provenance={"created_by": user, "created_via": "admin"})
    _apply_context(db, p, req.model_dump(exclude_unset=True))
    p.themes = [PhraseTheme(theme_code=c, source="researcher", status="approved") for c in req.codes if c in kb.themes]
    db.add(p)
    _audit(db, user, "phrase", pid, "create", after=_snapshot(p), note=req.note)
    db.commit()
    get_corpus_index().refresh(db, [p.id])
    return views.phrase_detail(db, p)


@router.put("/phrases/{phrase_id}")
def update_phrase(phrase_id: int, req: PhraseUpdate, db: Session = Depends(get_db), user: str = Depends(require_admin)) -> dict:
    p = _get_phrase(db, phrase_id)
    before = _snapshot(p)
    data = req.model_dump(exclude_unset=True)
    if "text_nepali" in data and data["text_nepali"]:
        text = normalize_text(data["text_nepali"])
        p.text_nepali, p.match_key = text, match_key(text)
        p.transliteration_auto = transliterate(text)
        p.places_mentioned = places_mentioned(db, text)
        if p.status == "text_missing":
            p.status = "active"
    if "transliteration" in data:
        p.transliteration = data["transliteration"]
    if "translation_normalized" in data:
        p.translation_normalized = data["translation_normalized"]
        p.translation = data["translation_normalized"] or p.translation_original
    if "coding" in data and data["coding"] is not None:
        p.coding = {**(p.coding or {}), **data["coding"]}
    for key in ("needs_review", "review_reason", "status"):
        if key in data and data[key] is not None:
            setattr(p, key, data[key])
    _apply_context(db, p, data)
    p.updated_by = user
    _audit(db, user, "phrase", p.id, "update", before=before, after=_snapshot(p), note=req.note)
    db.commit()
    get_corpus_index().refresh(db, [p.id])
    return views.phrase_detail(db, p)


@router.delete("/phrases/{phrase_id}")
def archive_phrase(phrase_id: int, db: Session = Depends(get_db), user: str = Depends(require_admin),
                   note: str | None = None) -> dict:
    """Archive (soft-delete). Corpus records are never destroyed; restore with PUT status=active."""
    p = _get_phrase(db, phrase_id)
    before = _snapshot(p)
    p.status, p.updated_by = "archived", user
    _audit(db, user, "phrase", p.id, "archive", before=before, after=_snapshot(p), note=note)
    db.commit()
    get_corpus_index().refresh(db, [p.id])
    return {"id": p.id, "status": p.status}


class ThemeDecision(BaseModel):
    code: str
    status: Literal["approved", "rejected", "proposed"]
    source: Literal["corpus", "ai", "researcher"] = "researcher"
    rationale: str | None = None


@router.put("/phrases/{phrase_id}/themes")
def decide_theme(phrase_id: int, req: ThemeDecision, db: Session = Depends(get_db), user: str = Depends(require_admin)) -> dict:
    kb = get_knowledge()
    if req.code not in kb.themes:
        raise HTTPException(422, f"Unknown theme code {req.code}.")
    p = _get_phrase(db, phrase_id)
    before = _snapshot(p)
    row = next((t for t in p.themes if t.theme_code == req.code and t.source == req.source), None)
    if row is None:
        row = PhraseTheme(theme_code=req.code, source=req.source)
        p.themes.append(row)
    row.status, row.rationale = req.status, req.rationale or row.rationale
    p.updated_by = user
    _audit(db, user, "phrase_theme", f"{p.id}:{req.code}", f"theme_{req.status}", before=before, after=_snapshot(p), note=req.rationale)
    db.commit()
    get_corpus_index().refresh(db, [p.id])
    return views.phrase_detail(db, p)


class ApproveRequest(BaseModel):
    note: str | None = None


@router.post("/phrases/{phrase_id}/approve")
def approve_phrase(phrase_id: int, req: ApproveRequest, db: Session = Depends(get_db), user: str = Depends(require_admin)) -> dict:
    """Mark the entry reviewed: proposed themes and labels become approved."""
    p = _get_phrase(db, phrase_id)
    before = _snapshot(p)
    for t in p.themes:
        if t.status == "proposed":
            t.status = "approved"
    for l in p.labels:
        if l.status == "proposed":
            l.status = "approved"
    p.needs_review, p.updated_by = False, user
    _audit(db, user, "phrase", p.id, "approve", before=before, after=_snapshot(p), note=req.note)
    db.commit()
    get_corpus_index().refresh(db, [p.id])
    return views.phrase_detail(db, p)


@router.post("/phrases/{phrase_id}/reanalyze")
async def reanalyze(phrase_id: int, db: Session = Depends(get_db), user: str = Depends(require_admin)) -> dict:
    """Run the current engine on this entry and attach its theme codes as AI suggestions for review."""
    p = _get_phrase(db, phrase_id)
    try:
        result = await get_engine().analyze(db, p.searchable_text, use_cache=False)
    except AnalysisInputError as exc:
        raise HTTPException(422, str(exc)) from exc
    existing = {(t.theme_code, t.source) for t in p.themes}
    added = []
    for t in result.payload.themes:
        if (t.code, "ai") not in existing:
            p.themes.append(PhraseTheme(theme_code=t.code, source="ai", status="proposed", confidence=t.confidence,
                                        rationale=t.rationale))
            added.append(t.code)
    _audit(db, user, "phrase", p.id, "reanalyze", after={"analysis_id": result.id, "ai_codes_added": added,
                                                          "engine": result.engine.mode})
    db.commit()
    return {"analysis_id": result.id, "engine": result.engine.mode, "ai_codes_added": added,
            "phrase": views.phrase_detail(db, p)}


# --- Submissions (public contributions, OCR corrections) ----------------------------------


def _submission_out(db: Session, s: Submission) -> dict:
    vehicle = db.get(VehicleType, s.vehicle_type_id) if s.vehicle_type_id else None
    district = views.district_by_id(db, s.district_id)
    return {"id": s.id, "text": s.text, "ocr_text": s.ocr_text, "ocr_provider": s.ocr_provider, "status": s.status,
            "vehicle_type": vehicle.slug if vehicle else None, "district": district.name_en if district else None,
            "district_id": s.district_id, "province_id": s.province_id, "locality": s.locality,
            "analysis_id": s.analysis_id, "phrase_id": s.phrase_id, "reviewer_note": s.reviewer_note,
            "created_at": s.created_at.isoformat()}


@router.get("/submissions")
def submissions(status: str | None = "pending", db: Session = Depends(get_db), _: str = Depends(require_admin)) -> list[dict]:
    stmt = select(Submission).order_by(Submission.created_at.desc())
    if status:
        stmt = stmt.where(Submission.status == status)
    return [_submission_out(db, s) for s in db.scalars(stmt)]


class SubmissionDecision(BaseModel):
    text: str | None = Field(None, description="Corrected text (e.g. fixing OCR).")
    note: str | None = None


@router.post("/submissions/{submission_id}/accept")
def accept_submission(submission_id: str, req: SubmissionDecision, db: Session = Depends(get_db),
                      user: str = Depends(require_admin)) -> dict:
    s = db.get(Submission, submission_id)
    if not s or s.status != "pending":
        raise HTTPException(404, "Pending submission not found.")
    text = normalize_text(req.text or s.text)
    pid, corpus_id = _next_corpus_id(db)
    analysis = db.get(Analysis, s.analysis_id) if s.analysis_id else None
    payload = (analysis.result or {}).get("payload", {}) if analysis else {}
    p = Phrase(id=pid, corpus_id=corpus_id, status="active", text_nepali=text, match_key=match_key(text),
               transliteration_auto=transliterate(text), translation=payload.get("contextual_translation") or None,
               coding={}, source="public-submission", needs_review=True,
               review_reason="Public submission; AI themes need review.", vehicle_type_id=s.vehicle_type_id,
               province_id=s.province_id, district_id=s.district_id, municipality_id=s.municipality_id,
               locality=s.locality, places_mentioned=places_mentioned(db, text), updated_by=user,
               provenance={"submission_id": s.id, "ocr_provider": s.ocr_provider, "accepted_by": user})
    p.themes = [PhraseTheme(theme_code=t["code"], source="ai", status="proposed", confidence=t.get("confidence"),
                            rationale=t.get("rationale")) for t in payload.get("themes", []) if t.get("code") in get_knowledge().themes]
    db.add(p)
    s.status, s.phrase_id, s.reviewer_note = "accepted", pid, req.note
    if req.text and normalize_text(req.text) != s.text:
        _audit(db, user, "submission", s.id, "correct_text", before={"text": s.text}, after={"text": text})
        s.text = text
    _audit(db, user, "submission", s.id, "accept", after={"phrase_id": pid}, note=req.note)
    db.commit()
    get_corpus_index().refresh(db, [pid])
    return {"submission": _submission_out(db, s), "phrase": views.phrase_summary(p)}


@router.post("/submissions/{submission_id}/reject")
def reject_submission(submission_id: str, req: SubmissionDecision, db: Session = Depends(get_db),
                      user: str = Depends(require_admin)) -> dict:
    s = db.get(Submission, submission_id)
    if not s or s.status != "pending":
        raise HTTPException(404, "Pending submission not found.")
    s.status, s.reviewer_note = "rejected", req.note
    _audit(db, user, "submission", s.id, "reject", note=req.note)
    db.commit()
    return _submission_out(db, s)


# --- Taxonomy, categories, references ---------------------------------------------------


class ThemeIn(BaseModel):
    code: str = Field(..., pattern=r"^[A-Z][A-Z_]{2,39}$")
    label_en: str
    label_ne: str
    group: Literal["love", "social", "economic", "political", "gender_power", "cultural", "philosophical", "rhetorical"]
    definition: str
    keywords_en: list[str] = []
    keywords_ne: list[str] = []


@router.post("/themes", status_code=201)
def add_theme(req: ThemeIn, db: Session = Depends(get_db), user: str = Depends(require_admin)) -> dict:
    kb = get_knowledge()
    if req.code in kb.themes:
        raise HTTPException(409, "A theme with this code already exists.")
    db.add(Theme(code=req.code, label_en=req.label_en, label_ne=req.label_ne, group=req.group, origin="Researcher",
                 definition=req.definition))
    _audit(db, user, "theme", req.code, "create", after=req.model_dump())
    db.commit()
    kb.add_theme({**req.model_dump(), "origin": "Researcher"})
    prompts.system_prompt.cache_clear()
    return kb.themes[req.code]


class ReferenceIn(BaseModel):
    id: str = Field(..., pattern=r"^[a-z0-9-]{3,80}$")
    title: str
    authors: str
    year: int | None = None
    source: str
    url: str | None = None
    kind: str = "article"
    topics: list[str] = []
    note: str | None = None


@router.post("/references", status_code=201)
def add_reference(req: ReferenceIn, db: Session = Depends(get_db), user: str = Depends(require_admin)) -> dict:
    if req.url and not re.match(r"^https?://", req.url):
        raise HTTPException(422, "Reference URLs must start with http:// or https://")
    ref = db.get(Reference, req.id) or Reference(id=req.id)
    for key, value in req.model_dump().items():
        setattr(ref, key, value)
    ref.level = 2
    db.merge(ref)
    _audit(db, user, "reference", req.id, "upsert", after=req.model_dump())
    db.commit()
    get_knowledge().add_reference(req.model_dump())
    return req.model_dump()


@router.get("/taxonomy/versions")
def taxonomy_versions(db: Session = Depends(get_db), _: str = Depends(require_admin)) -> list[dict]:
    return [{"id": t.id, "version": t.version, "is_active": t.is_active, "note": t.note, "created_at": t.created_at.isoformat(),
             "themes": len(t.data.get("themes", []))} for t in db.scalars(select(TaxonomyVersion).order_by(TaxonomyVersion.id))]


class TaxonomyDraft(BaseModel):
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    data: dict
    note: str | None = None


@router.post("/taxonomy/versions", status_code=201)
def save_taxonomy_draft(req: TaxonomyDraft, db: Session = Depends(get_db), user: str = Depends(require_admin)) -> dict:
    """Store a proposed taxonomy version for review. Deploy it by committing it to taxonomy/ and setting TAXONOMY_PATH."""
    missing = [k for k in ("themes", "dimensions", "emotion_families", "love_types", "power_stances") if k not in req.data]
    if missing:
        raise HTTPException(422, f"Taxonomy is missing sections: {', '.join(missing)}")
    if db.scalar(select(TaxonomyVersion).where(TaxonomyVersion.version == req.version)):
        raise HTTPException(409, "This version already exists.")
    tv = TaxonomyVersion(version=req.version, data=req.data, is_active=False, note=req.note)
    db.add(tv)
    _audit(db, user, "taxonomy", req.version, "draft", note=req.note)
    db.commit()
    return {"id": tv.id, "version": tv.version, "is_active": False}


# --- Geography ----------------------------------------------------------------------------


@router.post("/municipalities/import")
async def municipalities_import(file: UploadFile = File(...), source: str = Query(..., min_length=3),
                                db: Session = Depends(get_db), user: str = Depends(require_admin)) -> dict:
    raw = (await file.read(5 * 1024 * 1024)).decode("utf-8-sig")
    result = import_municipalities(db, raw, source)
    _audit(db, user, "municipalities", source, "import", after=result)
    db.commit()
    return result


# --- Corpus maintenance, export, analytics, audit ----------------------------------------------


@router.post("/import-corpus")
def reimport_corpus(force: bool = False, db: Session = Depends(get_db), user: str = Depends(require_admin)) -> dict:
    result = import_corpus(db, force=force)
    _audit(db, user, "corpus", "processed/corpus.json", "import", after=result)
    db.commit()
    get_corpus_index().build(db)
    return result


@router.get("/export")
def export(format: Literal["json", "csv"] = "json", db: Session = Depends(get_db), user: str = Depends(require_admin)) -> Response:
    rows = []
    for p in views.list_phrases(db, include_archived=True):
        rows.append({
            **views.phrase_summary(p),
            "text_original": p.text_nepali,
            "translation_original": p.translation_original,
            "translation_normalized": p.translation_normalized,
            "themes": [{"code": t.theme_code, "source": t.source, "status": t.status} for t in p.themes],
            "coding": p.coding,
            "review_reason": p.review_reason,
            "provenance": p.provenance,
            "updated_by": p.updated_by,
        })
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    if format == "json":
        body = json.dumps({"exported_at": stamp, "taxonomy_version": get_knowledge().version, "records": rows},
                          ensure_ascii=False, indent=2)
        return Response(body, media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="nvl-corpus-{stamp}.json"'})
    buf = io.StringIO()
    cols = ["corpus_id", "status", "text", "transliteration", "translation", "codes", "approved_codes", "valence",
            "emotions", "confidence", "needs_review", "review_priority", "review_reason", "vehicle_type", "district", "source"]
    writer = csv.DictWriter(buf, fieldnames=cols)
    writer.writeheader()
    for r in rows:
        writer.writerow({
            **{k: r.get(k) for k in cols},
            "codes": "|".join(r["codes"]),
            "approved_codes": "|".join(t["code"] for t in r["themes"] if t["status"] == "approved"),
            "emotions": "|".join(r["emotions"]),
        })
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="nvl-corpus-{stamp}.csv"'})


@router.get("/analytics")
def analytics(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db), _: str = Depends(require_admin)) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.scalars(select(Analysis).where(Analysis.created_at >= since)).all()
    per_day: dict[str, int] = {}
    engines: dict[str, int] = {}
    theme_counts: dict[str, int] = {}
    durations = []
    for a in rows:
        day = a.created_at.date().isoformat()
        per_day[day] = per_day.get(day, 0) + 1
        engines[a.engine] = engines.get(a.engine, 0) + 1
        if a.duration_ms:
            durations.append(a.duration_ms)
        for t in (a.result or {}).get("payload", {}).get("themes", []):
            theme_counts[t["code"]] = theme_counts.get(t["code"], 0) + 1
    durations.sort()
    return {
        "days": days,
        "analyses": len(rows),
        "matched_corpus": sum(1 for a in rows if a.phrase_id),
        "per_day": [{"day": d, "count": c} for d, c in sorted(per_day.items())],
        "engines": engines,
        "median_ms": durations[len(durations) // 2] if durations else None,
        "top_themes": sorted(({"code": c, "count": n} for c, n in theme_counts.items()), key=lambda x: -x["count"])[:10],
        "submissions": {s: db.scalar(select(func.count(Submission.id)).where(Submission.status == s)) or 0
                        for s in ("pending", "accepted", "rejected")},
        "corpus": views.corpus_stats(db) | {"cooccurrence": None},
    }


@router.get("/audit")
def audit(limit: int = Query(100, ge=1, le=1000), target_id: str | None = None,
          db: Session = Depends(get_db), _: str = Depends(require_admin)) -> list[dict]:
    stmt = select(ReviewEvent).order_by(ReviewEvent.id.desc()).limit(limit)
    if target_id:
        stmt = stmt.where(ReviewEvent.target_id == target_id)
    return [{"id": e.id, "target_type": e.target_type, "target_id": e.target_id, "action": e.action, "reviewer": e.reviewer,
             "note": e.note, "before": e.before, "after": e.after, "created_at": e.created_at.isoformat()} for e in db.scalars(stmt)]
