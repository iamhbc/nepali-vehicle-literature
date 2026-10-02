"""Relational data model.

Design notes
------------
* ``Phrase`` is a corpus record. Its researcher coding is kept whole in
  ``coding`` (JSON, mirrors the codebook) so nothing in the original workbook is
  lost, while the queryable parts are normalized into ``PhraseTheme`` and
  ``PhraseLabel``.
* Every label carries ``source`` (corpus / ai / researcher) and ``status``
  (proposed / approved / rejected): this is the human-in-the-loop trail.
* Images are never stored; ``Submission`` keeps only text and optional metadata.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return uuid.uuid4().hex


# --- Directories --------------------------------------------------------------


class Province(Base):
    __tablename__ = "provinces"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_en: Mapped[str] = mapped_column(String(80))
    name_ne: Mapped[str] = mapped_column(String(80))
    districts: Mapped[list[District]] = relationship(back_populates="province", order_by="District.id")


class District(Base):
    __tablename__ = "districts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    province_id: Mapped[int] = mapped_column(ForeignKey("provinces.id"), index=True)
    name_en: Mapped[str] = mapped_column(String(80))
    name_ne: Mapped[str] = mapped_column(String(80))
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    province: Mapped[Province] = relationship(back_populates="districts")
    municipalities: Mapped[list[Municipality]] = relationship(back_populates="district")


class Municipality(Base):
    __tablename__ = "municipalities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id"), index=True)
    name_en: Mapped[str] = mapped_column(String(120))
    name_ne: Mapped[str | None] = mapped_column(String(120))
    # metropolitan / sub-metropolitan / municipality / rural municipality
    kind: Mapped[str | None] = mapped_column(String(40))
    source: Mapped[str | None] = mapped_column(String(200))
    district: Mapped[District] = relationship(back_populates="municipalities")


class VehicleType(Base):
    __tablename__ = "vehicle_types"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name_en: Mapped[str] = mapped_column(String(80))
    name_ne: Mapped[str] = mapped_column(String(80))


# --- Taxonomy -------------------------------------------------------------------


class TaxonomyVersion(Base):
    __tablename__ = "taxonomy_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(20), unique=True)
    data: Mapped[dict] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Theme(Base):
    __tablename__ = "themes"
    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    label_en: Mapped[str] = mapped_column(String(80))
    label_ne: Mapped[str] = mapped_column(String(80))
    group: Mapped[str] = mapped_column(String(40))
    origin: Mapped[str] = mapped_column(String(20))
    definition: Mapped[str] = mapped_column(Text)


class Reference(Base):
    __tablename__ = "references"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[str] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(40))
    level: Mapped[int] = mapped_column(Integer, default=2)
    topics: Mapped[list] = mapped_column(JSON, default=list)
    note: Mapped[str | None] = mapped_column(Text)


# --- Corpus ----------------------------------------------------------------------


class Phrase(Base):
    __tablename__ = "phrases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    corpus_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | text_missing | archived

    text_nepali: Mapped[str] = mapped_column(Text)
    text_candidate: Mapped[str | None] = mapped_column(Text)
    match_key: Mapped[str] = mapped_column(Text, index=True)
    transliteration: Mapped[str | None] = mapped_column(Text)
    transliteration_auto: Mapped[str | None] = mapped_column(Text)
    translation: Mapped[str | None] = mapped_column(Text)
    translation_original: Mapped[str | None] = mapped_column(Text)
    translation_normalized: Mapped[str | None] = mapped_column(Text)
    original_theme: Mapped[list] = mapped_column(JSON, default=list)

    coding: Mapped[dict] = mapped_column(JSON, default=dict)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    review_reason: Mapped[str | None] = mapped_column(Text)
    review_priority: Mapped[str | None] = mapped_column(String(40))
    qc_flags: Mapped[list] = mapped_column(JSON, default=list)
    clusters: Mapped[list] = mapped_column(JSON, default=list)
    variant_group: Mapped[str | None] = mapped_column(String(60))
    variant_relation: Mapped[str | None] = mapped_column(String(120))

    # Observation context (where the inscription was seen) — distinct from places it mentions.
    vehicle_type_id: Mapped[int | None] = mapped_column(ForeignKey("vehicle_types.id"))
    province_id: Mapped[int | None] = mapped_column(ForeignKey("provinces.id"))
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"))
    municipality_id: Mapped[int | None] = mapped_column(ForeignKey("municipalities.id"))
    locality: Mapped[str | None] = mapped_column(String(200))
    places_mentioned: Mapped[list] = mapped_column(JSON, default=list)

    source: Mapped[str] = mapped_column(String(200), default="research-corpus")
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    updated_by: Mapped[str | None] = mapped_column(String(80))

    themes: Mapped[list[PhraseTheme]] = relationship(back_populates="phrase", cascade="all, delete-orphan")
    labels: Mapped[list[PhraseLabel]] = relationship(back_populates="phrase", cascade="all, delete-orphan")
    vehicle_type: Mapped[VehicleType | None] = relationship()
    district: Mapped[District | None] = relationship()

    @property
    def searchable_text(self) -> str:
        return self.text_candidate if self.status == "text_missing" and self.text_candidate else self.text_nepali


class PhraseTheme(Base):
    __tablename__ = "phrase_themes"
    __table_args__ = (UniqueConstraint("phrase_id", "theme_code", "source"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phrase_id: Mapped[int] = mapped_column(ForeignKey("phrases.id", ondelete="CASCADE"), index=True)
    theme_code: Mapped[str] = mapped_column(ForeignKey("themes.code"), index=True)
    source: Mapped[str] = mapped_column(String(20))  # corpus | ai | researcher
    status: Mapped[str] = mapped_column(String(20), default="proposed")  # proposed | approved | rejected
    confidence: Mapped[str | None] = mapped_column(String(10))
    rationale: Mapped[str | None] = mapped_column(Text)
    phrase: Mapped[Phrase] = relationship(back_populates="themes")


class PhraseLabel(Base):
    """A label on any analytical dimension (emotion, love, gender_power, ...)."""

    __tablename__ = "phrase_labels"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phrase_id: Mapped[int] = mapped_column(ForeignKey("phrases.id", ondelete="CASCADE"), index=True)
    dimension: Mapped[str] = mapped_column(String(40), index=True)
    label: Mapped[str] = mapped_column(String(160), index=True)
    source: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="proposed")
    confidence: Mapped[str | None] = mapped_column(String(10))
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    explanation: Mapped[str | None] = mapped_column(Text)
    phrase: Mapped[Phrase] = relationship(back_populates="labels")


class PhraseEmbedding(Base):
    __tablename__ = "phrase_embeddings"
    __table_args__ = (UniqueConstraint("phrase_id", "model"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phrase_id: Mapped[int] = mapped_column(ForeignKey("phrases.id", ondelete="CASCADE"), index=True)
    model: Mapped[str] = mapped_column(String(120))
    dim: Mapped[int] = mapped_column(Integer)
    vector: Mapped[list] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))


# --- Analysis, submissions, review -------------------------------------------------


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    cache_key: Mapped[str] = mapped_column(String(64), index=True)
    input_text: Mapped[str] = mapped_column(Text)
    match_key: Mapped[str] = mapped_column(Text)
    engine: Mapped[str] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(80))
    taxonomy_version: Mapped[str] = mapped_column(String(20))
    result: Mapped[dict] = mapped_column(JSON)
    phrase_id: Mapped[int | None] = mapped_column(ForeignKey("phrases.id", ondelete="SET NULL"))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Submission(Base):
    """A public contribution. Text only — photographs are processed in memory and discarded."""

    __tablename__ = "submissions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    text: Mapped[str] = mapped_column(Text)
    ocr_text: Mapped[str | None] = mapped_column(Text)
    ocr_provider: Mapped[str | None] = mapped_column(String(40))
    vehicle_type_id: Mapped[int | None] = mapped_column(ForeignKey("vehicle_types.id"))
    province_id: Mapped[int | None] = mapped_column(ForeignKey("provinces.id"))
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"))
    municipality_id: Mapped[int | None] = mapped_column(ForeignKey("municipalities.id"))
    locality: Mapped[str | None] = mapped_column(String(200))
    analysis_id: Mapped[str | None] = mapped_column(ForeignKey("analyses.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | accepted | rejected
    phrase_id: Mapped[int | None] = mapped_column(ForeignKey("phrases.id", ondelete="SET NULL"))
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ReviewEvent(Base):
    """Append-only audit log of researcher actions."""

    __tablename__ = "review_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(40))
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    reviewer: Mapped[str] = mapped_column(String(80))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


__all__ = [
    "Analysis",
    "District",
    "Municipality",
    "Phrase",
    "PhraseEmbedding",
    "PhraseLabel",
    "PhraseTheme",
    "Province",
    "Reference",
    "ReviewEvent",
    "Submission",
    "TaxonomyVersion",
    "Theme",
    "VehicleType",
]
