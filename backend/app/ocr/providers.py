"""OCR providers for Nepali (Devanagari) vehicle inscriptions."""

from __future__ import annotations

import asyncio
import logging
import shutil
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from ..analysis.llm import AnthropicProvider, LLMError, image_block, parse_model
from ..analysis.prompts import OCR_PROMPT
from ..analysis.schema import strict_json_schema
from ..config import Settings, get_settings
from .image import PreparedImage

log = logging.getLogger(__name__)


class OCRUnavailable(RuntimeError):
    pass


class OCRFailed(RuntimeError):
    pass


class OCRLine(BaseModel):
    text: str
    confidence: Literal["high", "medium", "low"]


class OCRPayload(BaseModel):
    lines: list[OCRLine]
    script: str = Field(description="Main script seen, e.g. 'Devanagari', 'Latin', 'mixed', 'none'.")
    legibility: Literal["high", "medium", "low"]
    uncertain_segments: list[str]
    other_text: list[str] = Field(description="Plates, phone numbers, brand names and other non-inscription text.")
    notes: str


class OCRResult(BaseModel):
    text: str
    lines: list[OCRLine]
    legibility: Literal["high", "medium", "low"]
    uncertain_segments: list[str]
    other_text: list[str]
    notes: str
    provider: str


class OCRProvider(Protocol):
    name: str

    async def read(self, image: PreparedImage) -> OCRResult: ...


class ClaudeVisionOCR:
    name = "anthropic-vision"

    def __init__(self, settings: Settings) -> None:
        self.llm = AnthropicProvider(settings)
        self.schema = strict_json_schema(OCRPayload)

    async def read(self, image: PreparedImage) -> OCRResult:
        content = [image_block(image.data, image.media_type), {"type": "text", "text": "Transcribe the inscription."}]
        try:
            response = await self.llm.structured(OCR_PROMPT, content, self.schema, max_tokens=4000)
            payload = parse_model(OCRPayload, response.data)
        except LLMError as exc:
            raise OCRFailed(str(exc)) from exc
        lines = [l for l in payload.lines if l.text.strip()]
        return OCRResult(
            text="\n".join(l.text.strip() for l in lines), lines=lines, legibility=payload.legibility,
            uncertain_segments=payload.uncertain_segments, other_text=payload.other_text, notes=payload.notes,
            provider=f"{self.name}:{response.model}",
        )


class TesseractOCR:
    """Local Tesseract with the 'nep' traineddata. Weaker on painted, stylised lettering."""

    name = "tesseract"

    def __init__(self, settings: Settings) -> None:
        self.cmd = settings.tesseract_cmd
        self.lang = settings.tesseract_lang
        if not shutil.which(self.cmd):
            raise OCRUnavailable("Tesseract is not installed on the server.")

    async def read(self, image: PreparedImage) -> OCRResult:
        proc = await asyncio.create_subprocess_exec(
            self.cmd, "stdin", "stdout", "-l", self.lang, "--psm", "6", "tsv",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(image.data), timeout=60)
        if proc.returncode != 0:
            raise OCRFailed(f"Tesseract failed: {err.decode(errors='ignore')[:200]}")
        rows = [r.split("\t") for r in out.decode("utf-8", errors="ignore").splitlines()[1:]]
        lines: dict[tuple[str, str, str], list[tuple[str, float]]] = {}
        for r in rows:
            if len(r) == 12 and r[11].strip():
                lines.setdefault((r[2], r[3], r[4]), []).append((r[11], float(r[10])))
        ocr_lines = []
        for words in lines.values():
            conf = sum(c for _, c in words) / len(words)
            level = "high" if conf >= 80 else "medium" if conf >= 55 else "low"
            ocr_lines.append(OCRLine(text=" ".join(w for w, _ in words), confidence=level))
        overall = min((l.confidence for l in ocr_lines), default="low", key=["low", "medium", "high"].index)
        return OCRResult(text="\n".join(l.text for l in ocr_lines), lines=ocr_lines, legibility=overall,
                         uncertain_segments=[l.text for l in ocr_lines if l.confidence == "low"], other_text=[],
                         notes="Read with Tesseract (nep).", provider=self.name)


_provider: OCRProvider | None = None


def get_ocr_provider() -> OCRProvider:
    global _provider
    if _provider is None:
        s = get_settings()
        if s.ocr_provider == "anthropic":
            if not s.anthropic_api_key:
                raise OCRUnavailable("Photo reading is not configured on this server.")
            _provider = ClaudeVisionOCR(s)
        elif s.ocr_provider == "tesseract":
            _provider = TesseractOCR(s)
        else:
            raise OCRUnavailable("Photo reading is turned off on this server.")
    return _provider
