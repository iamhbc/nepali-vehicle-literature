"""Public, login-free API."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..analysis.engine import AnalysisInputError, get_engine
from ..analysis.schema import AnalysisResult
from ..config import get_settings
from ..db import SessionLocal, get_db
from ..knowledge import get_knowledge
from ..models import Analysis, District, Municipality, Phrase, Submission, VehicleType
from ..nlp.normalize import normalize_text
from ..ocr.image import ImageError, prepare_image
from ..ocr.providers import OCRFailed, OCRUnavailable, get_ocr_provider
from ..retrieval.search import get_corpus_index
from ..services import views
from ..services.ratelimit import client_key, limiter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["public"])


class AnalyzeContext(BaseModel):
    vehicle_type: str | None = Field(None, description="Vehicle type slug, e.g. 'truck'.")
    province_id: int | None = None
    district_id: int | None = None
    municipality_id: int | None = None
    locality: str | None = Field(None, max_length=200)


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    context: AnalyzeContext | None = None
    contribute: bool = Field(False, description="Offer this inscription to the researchers for the corpus.")
    ocr_text: str | None = Field(None, max_length=2000, description="Raw OCR output, if the text came from a photo.")
    ocr_provider: str | None = None


def _limit_analysis(request: Request) -> None:
    s = get_settings()
    if get_engine().mode == "llm":
        limiter.check(f"analyze:{client_key(request)}", s.rate_limit_analyze_per_hour, 3600)


def _context_for_llm(db: Session, ctx: AnalyzeContext | None) -> dict | None:
    if not ctx:
        return None
    out: dict = {}
    if ctx.vehicle_type:
        v = db.scalar(select(VehicleType).where(VehicleType.slug == ctx.vehicle_type))
        out["vehicle_type"] = v.name_en if v else None
    if ctx.district_id and (d := db.get(District, ctx.district_id)):
        out["district"] = f"{d.name_en} ({d.province.name_en} Province)"
    if ctx.municipality_id and (m := db.get(Municipality, ctx.municipality_id)):
        out["municipality"] = m.name_en
    if ctx.locality:
        out["locality"] = ctx.locality
    return out or None


def _record_submission(db: Session, req: AnalyzeRequest, analysis_id: str | None) -> str:
    ctx = req.context or AnalyzeContext()
    vehicle = db.scalar(select(VehicleType).where(VehicleType.slug == ctx.vehicle_type)) if ctx.vehicle_type else None
    sub = Submission(
        text=normalize_text(req.text), ocr_text=req.ocr_text, ocr_provider=req.ocr_provider,
        vehicle_type_id=vehicle.id if vehicle else None, province_id=ctx.province_id, district_id=ctx.district_id,
        municipality_id=ctx.municipality_id, locality=ctx.locality, analysis_id=analysis_id,
    )
    db.add(sub)
    db.commit()
    return sub.id


# --- Status & reference data -------------------------------------------------------


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    s = get_settings()
    index = get_corpus_index()
    return {
        "status": "ok",
        "engine": get_engine().mode,
        "model": s.llm_model if get_engine().mode == "llm" else None,
        "ocr": s.ocr_provider if (s.ocr_provider != "anthropic" or s.anthropic_api_key) else "none",
        "corpus_size": len(index.meta),
        "embedding": index.embedder.name,
        "taxonomy_version": get_knowledge().version,
        "admin_enabled": s.admin_enabled,
    }


@router.get("/meta")
def meta(db: Session = Depends(get_db)) -> dict:
    kb = get_knowledge()
    s = get_settings()
    return {
        "engine": get_engine().mode,
        "ocr_available": s.ocr_provider == "tesseract" or (s.ocr_provider == "anthropic" and bool(s.anthropic_api_key)),
        "max_phrase_chars": s.max_phrase_chars,
        "taxonomy_version": kb.version,
        "dimensions": kb.taxonomy["dimensions"],
        "themes": kb.taxonomy["themes"],
        "emotion_families": kb.taxonomy["emotion_families"],
        "love_types": kb.taxonomy["love_types"],
        "confidence_levels": kb.taxonomy["confidence_levels"],
        "epistemic_kinds": kb.taxonomy["epistemic_kinds"],
    }


@router.get("/examples")
def examples(db: Session = Depends(get_db)) -> list[dict]:
    return views.example_phrases(db)


@router.get("/taxonomy")
def taxonomy() -> dict:
    return get_knowledge().taxonomy


@router.get("/concepts")
def concepts() -> list[dict]:
    return get_knowledge().concepts


@router.get("/references")
def references() -> list[dict]:
    return get_knowledge().references


@router.get("/locations")
def locations(db: Session = Depends(get_db)) -> list[dict]:
    return views.location_tree(db)


@router.get("/locations/districts/{district_id}/municipalities")
def municipalities(district_id: int, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Municipality).where(Municipality.district_id == district_id).order_by(Municipality.name_en))
    return [{"id": m.id, "name_en": m.name_en, "name_ne": m.name_ne, "kind": m.kind} for m in rows]


@router.get("/vehicles")
def vehicles(db: Session = Depends(get_db)) -> list[dict]:
    return views.vehicle_list(db)


# --- Analysis ------------------------------------------------------------------------


@router.post("/analyze", response_model=AnalysisResult)
async def analyze(req: AnalyzeRequest, request: Request, db: Session = Depends(get_db)) -> AnalysisResult:
    _limit_analysis(request)
    try:
        result = await get_engine().analyze(db, req.text, _context_for_llm(db, req.context))
    except AnalysisInputError as exc:
        raise HTTPException(422, str(exc)) from exc
    if req.contribute:
        _record_submission(db, req, result.id if result.id != "preliminary" else None)
    return result


@router.post("/analyze/stream")
async def analyze_stream(req: AnalyzeRequest, request: Request, db: Session = Depends(get_db)) -> StreamingResponse:
    """Server-sent events: ``stage`` (progress), ``preliminary`` (instant baseline), ``result``, ``error``."""
    _limit_analysis(request)
    engine = get_engine()
    try:
        engine.validate(normalize_text(req.text))
    except AnalysisInputError as exc:
        raise HTTPException(422, str(exc)) from exc
    context = _context_for_llm(db, req.context)

    async def events():
        # The stream outlives the request dependency, so it owns its session.
        session = SessionLocal()
        try:
            async for ev in engine.stream(session, req.text, context):
                if ev["event"] == "result" and req.contribute:
                    ev["data"]["submission_id"] = _record_submission(session, req, ev["data"].get("id"))
                yield f"event: {ev['event']}\ndata: {json.dumps(ev['data'], ensure_ascii=False)}\n\n"
        except AnalysisInputError as exc:
            yield f"event: error\ndata: {json.dumps({'detail': str(exc)})}\n\n"
        except Exception:  # pragma: no cover - surfaced to the client, logged here
            log.exception("Streaming analysis failed")
            yield f"event: error\ndata: {json.dumps({'detail': 'The analysis failed unexpectedly. Please try again.'})}\n\n"
        finally:
            session.close()

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/analyses/{analysis_id}", response_model=AnalysisResult)
def get_analysis(analysis_id: str, db: Session = Depends(get_db)) -> AnalysisResult:
    row = db.get(Analysis, analysis_id)
    if not row:
        raise HTTPException(404, "Analysis not found.")
    return AnalysisResult.model_validate(row.result)


# --- OCR ---------------------------------------------------------------------------


async def _run_ocr(file: UploadFile, request: Request) -> dict:
    s = get_settings()
    limiter.check(f"ocr:{client_key(request)}", s.rate_limit_ocr_per_hour, 3600)
    raw = await file.read(int(s.ocr_max_upload_mb * 1024 * 1024) + 1)
    try:
        image = prepare_image(raw, int(s.ocr_max_upload_mb * 1024 * 1024))
    except ImageError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        del raw
    try:
        provider = get_ocr_provider()
        result = await provider.read(image)
    except OCRUnavailable as exc:
        raise HTTPException(503, f"{exc} You can type the inscription instead.") from exc
    except OCRFailed as exc:
        raise HTTPException(502, "We couldn't confidently read the inscription. Please type it instead.") from exc

    text = normalize_text(result.text)
    suggestions = []
    if text:
        index = get_corpus_index()
        match = index.find_match(text, threshold=0.6)
        if match:
            suggestions.append({"id": match[0].id, "corpus_id": match[0].corpus_id, "text": match[0].text,
                                "similarity": match[1], "reason": "Closely matches an inscription already in the corpus."})
    return {
        **result.model_dump(),
        "text": text,
        "readable": bool(text) and result.legibility != "low",
        "suggestions": suggestions,
        "image": {"width": image.width, "height": image.height, "metadata_stripped": True, "stored": False},
    }


@router.post("/ocr")
async def ocr(request: Request, file: UploadFile = File(...)) -> dict:
    """Read an inscription from a photo. The image is processed in memory and never stored."""
    return await _run_ocr(file, request)


@router.post("/analyze-image")
async def analyze_image(request: Request, file: UploadFile = File(...), auto_analyze: bool = Form(False),
                        db: Session = Depends(get_db)) -> dict:
    """OCR, then (only if ``auto_analyze``) analysis. The UI always shows OCR text for correction first."""
    ocr_result = await _run_ocr(file, request)
    out = {"ocr": ocr_result, "analysis": None}
    if auto_analyze and ocr_result["text"]:
        _limit_analysis(request)
        out["analysis"] = (await get_engine().analyze(db, ocr_result["text"])).model_dump(mode="json")
    return out


# --- Corpus ------------------------------------------------------------------------------


@router.get("/phrases")
def phrases(
    db: Session = Depends(get_db),
    theme: str | None = None,
    cluster: str | None = None,
    valence: str | None = None,
    needs_review: bool | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    rows = views.list_phrases(db, theme=theme, cluster=cluster, valence=valence, needs_review=needs_review)
    return {"total": len(rows), "items": [views.phrase_summary(p) for p in rows[offset: offset + limit]]}


@router.get("/phrases/{phrase_id}")
def phrase(phrase_id: int, db: Session = Depends(get_db)) -> dict:
    p = db.get(Phrase, phrase_id)
    if not p or p.status == "archived":
        raise HTTPException(404, "Corpus entry not found.")
    return views.phrase_detail(db, p)


@router.get("/related/{phrase_id}")
def related(phrase_id: int, k: int = Query(6, ge=1, le=20), db: Session = Depends(get_db)) -> list[dict]:
    p = db.get(Phrase, phrase_id)
    if not p:
        raise HTTPException(404, "Corpus entry not found.")
    hits = get_corpus_index().related(p.searchable_text, k=k, codes=views.active_codes(p), exclude={p.id})
    return [{"id": h.id, "corpus_id": h.meta.corpus_id, "text": h.meta.text, "translation": h.meta.translation,
             "score": h.score, "reasons": h.reasons, "codes": h.meta.codes} for h in hits]


@router.get("/search")
def search(q: str = Query(..., min_length=1, max_length=300), k: int = Query(12, ge=1, le=50),
           theme: str | None = None) -> dict:
    index = get_corpus_index()
    hits = index.search(q, k=k, theme=theme)
    kb = get_knowledge()
    expanded = kb.themes_for_query(q)
    return {
        "query": q,
        "interpreted_themes": [{"code": c, "label_en": kb.themes[c]["label_en"], "weight": w} for c, w in expanded.items()],
        "embedding": index.embedder.name,
        "results": [{"id": h.id, "corpus_id": h.meta.corpus_id, "text": h.meta.text, "translation": h.meta.translation,
                     "score": h.score, "vector_score": h.vector_score, "theme_score": h.theme_score,
                     "reasons": h.reasons, "codes": h.meta.codes, "needs_review": h.meta.needs_review} for h in hits],
        "note": None if hits else "We couldn't find a strong match in the current knowledge base.",
    }


@router.get("/themes")
def themes(db: Session = Depends(get_db)) -> list[dict]:
    stats = {t["code"]: t["count"] for t in views.corpus_stats(db)["themes"]}
    return [{**t, "count": stats.get(t["code"], 0)} for t in get_knowledge().taxonomy["themes"]]


@router.get("/themes/{code}")
def theme(code: str, db: Session = Depends(get_db)) -> dict:
    kb = get_knowledge()
    if code not in kb.themes:
        raise HTTPException(404, "Theme not found.")
    rows = views.list_phrases(db, theme=code)
    return {**kb.themes[code], "phrases": [views.phrase_summary(p) for p in rows],
            "references": kb.references_for({code})}


@router.get("/clusters")
def clusters() -> list[dict]:
    path = get_settings().data_dir / "processed" / "clusters.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


@router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    return views.corpus_stats(db)
