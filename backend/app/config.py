"""Application settings, read from environment variables (see ../.env.example)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # --- Storage -----------------------------------------------------------
    database_url: str = f"sqlite:///{REPO_ROOT / 'backend' / 'nvl.db'}"
    # "memory" keeps vectors in a numpy index rebuilt at startup (fine to ~100k
    # entries); "pgvector" queries Postgres directly.
    vector_backend: Literal["memory", "pgvector"] = "memory"

    # --- Knowledge files -----------------------------------------------------
    data_dir: Path = REPO_ROOT / "data"
    knowledge_dir: Path = REPO_ROOT / "knowledge-base"
    taxonomy_path: Path = REPO_ROOT / "taxonomy" / "taxonomy.v1.json"

    # --- LLM -------------------------------------------------------------------
    # "anthropic" uses Claude for structured analysis; "baseline" runs the
    # lexicon + corpus-similarity engine only (no external calls).
    llm_provider: Literal["anthropic", "baseline"] = "anthropic"
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    llm_model: str = "claude-opus-5-5"
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    llm_max_tokens: int = 16000
    llm_timeout_seconds: float = 180.0
    llm_retrieval_k: int = 6

    # --- Embeddings ----------------------------------------------------------
    embedding_provider: Literal["hashing", "sentence-transformers"] = "hashing"
    embedding_model: str = "intfloat/multilingual-e5-base"

    # --- OCR -------------------------------------------------------------------
    ocr_provider: Literal["anthropic", "tesseract", "none"] = "anthropic"
    ocr_max_upload_mb: float = 8.0
    tesseract_cmd: str = "tesseract"
    tesseract_lang: str = "nep"

    # --- Public API protection ---------------------------------------------
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    rate_limit_analyze_per_hour: int = 30
    rate_limit_ocr_per_hour: int = 20
    max_phrase_chars: int = 600
    # Honour X-Forwarded-For when running behind a trusted reverse proxy (Render, Fly, Railway).
    trust_proxy_headers: bool = False

    # --- Admin -----------------------------------------------------------------
    admin_username: str = "admin"
    # bcrypt hash; generate with `python scripts/hash_password.py`. Empty disables admin.
    admin_password_hash: str = ""
    jwt_secret: str = ""
    jwt_ttl_hours: int = 12

    @field_validator("database_url")
    @classmethod
    def _sqlalchemy_url(cls, v: str) -> str:
        # Hosts (Render, Railway, Neon, Supabase) hand out postgres:// URLs; use the psycopg 3 driver.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider == "anthropic" and bool(self.anthropic_api_key)

    @property
    def admin_enabled(self) -> bool:
        return bool(self.admin_password_hash and self.jwt_secret)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
