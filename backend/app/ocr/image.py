"""In-memory image preparation for OCR.

Images are decoded, rotated upright from EXIF, downscaled, and re-encoded as
JPEG. Re-encoding drops all metadata (EXIF, GPS, device). Nothing is written to
disk.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF", "BMP"}
MAX_SIDE = 1600
MAX_PIXELS = 40_000_000  # refuse decompression bombs


class ImageError(ValueError):
    pass


@dataclass
class PreparedImage:
    data: bytes
    media_type: str
    width: int
    height: int
    original_format: str
    metadata_stripped: bool


def prepare_image(raw: bytes, max_bytes: int) -> PreparedImage:
    if not raw:
        raise ImageError("The upload was empty.")
    if len(raw) > max_bytes:
        raise ImageError(f"The image is larger than {max_bytes // (1024 * 1024)} MB. Please use a smaller photo.")
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        img = Image.open(io.BytesIO(raw))
        fmt = img.format or "UNKNOWN"
        if fmt not in ALLOWED_FORMATS:
            raise ImageError(f"Unsupported image format ({fmt}). Please upload a JPEG, PNG or WebP photo.")
        img.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise ImageError("We couldn't open that file as an image.") from exc

    had_metadata = bool(img.info.get("exif") or getattr(img, "getexif", lambda: {})())
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    return PreparedImage(buf.getvalue(), "image/jpeg", img.width, img.height, fmt, had_metadata)
