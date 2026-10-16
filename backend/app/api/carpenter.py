"""POST /api/carpenter/pdf: the carpenter spec sheet for a validated design. Stateless; nothing is stored."""

from __future__ import annotations

import base64
import binascii
import io
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

from app.api.chat import _limiter
from app.api.errors import domain_error_response, error_response
from app.carpenter.pdf import build_pdf
from app.config import Settings, get_settings
from app.domain.apply import apply_ops
from app.domain.catalog import load_catalog
from app.domain.errors import DomainError
from app.services.signing import design_hash

router = APIRouter(prefix="/api/carpenter")

MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_IMAGE_SIDE = 4096
MAX_BODY_BYTES = 9 * 1024 * 1024  # two base64 images (4/3 overhead) plus the design
_PNG_PREFIX = "data:image/png;base64,"
_MAX_DATA_URL = len(_PNG_PREFIX) + (MAX_IMAGE_BYTES * 4) // 3 + 4


class Images(BaseModel):
    model_config = ConfigDict(extra="forbid")
    closed: Annotated[str, Field(max_length=_MAX_DATA_URL)]
    interior: Annotated[str, Field(max_length=_MAX_DATA_URL)]


class PdfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    design: dict
    images: Images


class _BadImage(Exception):
    pass


def _png(data_url: str) -> bytes:
    """Decode and verify a PNG data URL (format, byte size and pixel size; decompression-bomb safe)."""
    if not data_url.startswith(_PNG_PREFIX):
        raise _BadImage
    try:
        raw = base64.b64decode(data_url[len(_PNG_PREFIX):], validate=True)
    except (binascii.Error, ValueError):
        raise _BadImage from None
    if len(raw) > MAX_IMAGE_BYTES:
        raise _BadImage
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != "PNG" or max(image.size) > MAX_IMAGE_SIDE:
                raise _BadImage
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError, ValueError):
        raise _BadImage from None
    return raw


@router.post("/pdf")
def carpenter_pdf(body: PdfRequest, request: Request, settings: Annotated[Settings, Depends(get_settings)]):
    client = request.client.host if request.client else "unknown"
    if not _limiter(settings.chat_rate_limit_per_minute).allow(client):
        return error_response(429, "RATE_LIMITED", "Too many requests. Please wait a minute and try again.")
    catalog = load_catalog()
    try:
        design = apply_ops(body.design, [], catalog)  # parse + full validation, canonical copy
    except DomainError as error:
        return domain_error_response(error)
    try:
        images = {"closed": _png(body.images.closed), "interior": _png(body.images.interior)}
    except _BadImage:
        return error_response(422, "INVALID_IMAGE", "The 3D images could not be read. Please try again.")
    today = date.today()
    pdf = build_pdf(design, catalog, images, reference=design_hash(design)[:8], today=today)
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="banai-wardrobe-{today:%Y%m%d}.pdf"',
        "Cache-Control": "no-store",
    })
