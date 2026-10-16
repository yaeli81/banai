"""Fonts and right-to-left text for the PDF (customer-provided names may be Hebrew or Arabic)."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from bidi import get_display
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"
_FONTS = Path(__file__).with_name("fonts")
_RTL = re.compile(r"[֐-ࣿיִ-﷿ﹰ-﻿]")


@lru_cache
def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont(FONT, str(_FONTS / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(_FONTS / "DejaVuSans-Bold.ttf")))
    addMapping(FONT, 0, 0, FONT)
    addMapping(FONT, 1, 0, FONT_BOLD)


def visual(text: str | None) -> str:
    """PDF text is drawn left to right: reorder RTL runs into visual order."""
    if not text:
        return ""
    return get_display(text) if _RTL.search(text) else text
