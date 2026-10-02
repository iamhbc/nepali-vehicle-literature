"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from .api import admin, public
from .config import get_settings
from .db import SessionLocal, init_db
from .knowledge import get_knowledge
from .models import Phrase, Reference, Theme
from .retrieval.search import get_corpus_index
from .services.corpus import import_corpus, seed_reference_data

log = logging.getLogger("nvl")


def merge_runtime_knowledge() -> None:
    """Re-register researcher-created themes and references stored in the database."""
    kb = get_knowledge()
    with SessionLocal() as db:
        for t in db.scalars(select(Theme)):
            if t.code not in kb.themes:
                kb.add_theme({"code": t.code, "label_en": t.label_en, "label_ne": t.label_ne, "group": t.group,
                              "origin": t.origin, "definition": t.definition})
        for r in db.scalars(select(Reference)):
            if r.id not in kb.references_by_id:
                kb.add_reference({"id": r.id, "title": r.title, "authors": r.authors, "year": r.year, "source": r.source,
                                  "url": r.url, "kind": r.kind, "topics": r.topics or [], "note": r.note})


def bootstrap() -> None:
    init_db()
    with SessionLocal() as db:
        seed_reference_data(db)
        if not db.scalar(select(Phrase.id).limit(1)):
            log.info("Empty corpus: importing data/processed/corpus.json")
            import_corpus(db)
        merge_runtime_knowledge()
        get_corpus_index().build(db)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    s = get_settings()
    logging.basicConfig(level=s.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    bootstrap()
    from .analysis.engine import get_engine

    log.info("Analysis engine: %s%s", get_engine().mode, f" ({s.llm_model})" if get_engine().mode == "llm" else "")
    if s.environment == "production" and not s.llm_enabled:
        log.warning("Running in production without an LLM provider: analyses use the baseline engine only.")
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="Nepali Vehicle Literature API",
        version="0.1.0",
        description="Multidimensional cultural, emotional, social and political analysis of Nepali expressions, "
        "grounded in a research corpus of vehicle inscriptions.",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=3600,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    @app.exception_handler(Exception)
    async def unhandled(_request: Request, exc: Exception):  # pragma: no cover
        log.exception("Unhandled error: %s", exc)
        return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)

    app.include_router(public.router)
    app.include_router(admin.auth_router)
    app.include_router(admin.router)
    return app


app = create_app()
