"""The carpenter PDF (A4 portrait): cover + 3D view, front elevation + interior view, detail tables."""

from __future__ import annotations

import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from app.carpenter.drawing import front_elevation
from app.carpenter.spec import build_spec
from app.carpenter.text import FONT, FONT_BOLD, register_fonts, visual

DISCLAIMER_LINES = ("Dimensions as designed by the customer, in millimetres. Not a manufacturing drawing.",
                    "Verify on site and against your manufacturing method before cutting.")
DISCLAIMER = " ".join(DISCLAIMER_LINES)
NOT_IN_DESIGN = ("Not part of the design (carpenter's choice): back panel, door thickness and gaps, joinery, "
                 "edge banding, hinges, runners, handles and other hardware.")
ACCENT = colors.HexColor("#b4532a")
INK = colors.HexColor("#2b211c")
MUTED = colors.HexColor("#6b5e57")
LINE = colors.HexColor("#e5dad2")
HEAD_BG = colors.HexColor("#f4ebe5")

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


def _styles() -> dict:
    register_fonts()
    base = ParagraphStyle("base", fontName=FONT, fontSize=9, leading=12, textColor=INK)
    return {
        "base": base,
        "title": ParagraphStyle("title", base, fontName=FONT_BOLD, fontSize=18, leading=22),
        "h2": ParagraphStyle("h2", base, fontName=FONT_BOLD, fontSize=12, leading=16, spaceBefore=6, spaceAfter=4),
        "muted": ParagraphStyle("muted", base, fontSize=8, leading=10.5, textColor=MUTED),
        "cell": ParagraphStyle("cell", base, fontSize=8, leading=10),
        "cellb": ParagraphStyle("cellb", base, fontName=FONT_BOLD, fontSize=8, leading=10),
    }


def _p(text, style) -> Paragraph:
    return Paragraph(escape(visual(str(text))), style)


def _table(rows: list[list], widths: list[float], s: dict) -> Table:
    data = [[_p(c, s["cellb"]) for c in rows[0]]] + [[_p(c, s["cell"]) for c in row] for row in rows[1:]]
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _image(png: bytes, max_w: float, max_h: float) -> Image:
    image = Image(io.BytesIO(png))
    ratio = min(max_w / image.imageWidth, max_h / image.imageHeight)
    image.drawWidth, image.drawHeight = image.imageWidth * ratio, image.imageHeight * ratio
    return image


def _footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(MARGIN, 15 * mm, PAGE_W - MARGIN, 15 * mm)
    canvas.setFont(FONT_BOLD, 7)
    canvas.setFillColor(ACCENT)
    canvas.drawString(MARGIN, 11.5 * mm, DISCLAIMER_LINES[0])
    canvas.drawString(MARGIN, 8.5 * mm, DISCLAIMER_LINES[1])
    canvas.setFont(FONT, 7)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(PAGE_W - MARGIN, 8.5 * mm, f"BanAI wardrobe {doc.reference} · page {doc.page}")
    canvas.restoreState()


def build_pdf(design: dict, catalog: dict, images: dict[str, bytes], reference: str, today: date | None = None) -> bytes:
    s = _styles()
    spec = build_spec(design, catalog)
    o, today = spec["overall"], today or date.today()
    story: list = []

    # Page 1: cover with the closed-door 3D view and the key numbers.
    story += [
        _p("Wardrobe specification for the carpenter", s["title"]),
        _p(f"{today.isoformat()} · design reference {reference}", s["muted"]),
        Spacer(1, 4 * mm),
        _image(images["closed"], CONTENT_W, 118 * mm),
        Spacer(1, 4 * mm),
        _p("Key dimensions (mm)", s["h2"]),
        _table([
            ["Item", "Value"],
            ["Overall width × height × depth", f"{o['width']} × {o['height']} × {o['depth']}"],
            ["Panel thickness (sides, top, bottom)", f"{spec['panel_thickness']}"],
            ["Interior width × height", f"{spec['interior']['width']} × {spec['interior']['height']}"],
            ["Compartments (left → right)", " | ".join(f"{c['name']} {c['width']}" for c in spec["compartments"])],
            ["Partitions", ", ".join(f"{p['name']} {p['thickness']}" for p in spec["partitions"]) or "none"],
            ["Doors", f"{spec['door_type']}, {len(spec['doors'])}" if spec["doors"] else spec["door_type"]],
            ["Interior items", f"{spec['counts']['shelves']} shelves, {spec['counts']['drawers']} drawers, "
                               f"{spec['counts']['rails']} hanging rails"],
            ["Carcass & interior finish", spec["finishes"]["carcass"]],
            ["Door finish", spec["finishes"]["doors"] if spec["doors"] else "—"],
        ], [70 * mm, CONTENT_W - 70 * mm], s),
        Spacer(1, 3 * mm),
        _p(NOT_IN_DESIGN, s["muted"]),
        PageBreak(),
    ]

    # Page 2: to-scale front elevation and the interior 3D view.
    story += [
        _p("Front elevation (doors removed)", s["h2"]),
        front_elevation(design, spec, CONTENT_W, 132 * mm),
        Spacer(1, 3 * mm),
        _p("Interior view (illustration)", s["h2"]),
        _image(images["interior"], CONTENT_W, 82 * mm),
        PageBreak(),
    ]

    # Page 3: every dimension, as tables.
    rows = [["Comp.", "Interior x (from → to)", "Width", "Item", "y", "Size", "Finish override"]]
    for c in spec["compartments"]:
        if not c["items"]:
            rows.append([c["name"], f"{c['x_from']} → {c['x_to']}", c["width"], "(empty)", "", "", ""])
        for i, item in enumerate(c["items"]):
            size = f"{item['size']} ({item['size_label']})" if item["size"] is not None else ""
            first = i == 0
            rows.append([c["name"] if first else "", f"{c['x_from']} → {c['x_to']}" if first else "",
                         c["width"] if first else "", item["kind"], item["y"], size, item["finish"] or ""])
    story += [
        _p("Compartments and interior items (mm)", s["h2"]),
        _p("x is measured from the inner face of the left side panel; y from the top face of the bottom panel "
           "to the underside of the item.", s["muted"]),
        Spacer(1, 2 * mm),
        _table(rows, [22 * mm, 32 * mm, 15 * mm, 24 * mm, 13 * mm, 30 * mm, CONTENT_W - 136 * mm], s),
        Spacer(1, 4 * mm),
        _p("Partitions (mm)", s["h2"]),
        _table([["Partition", "Between", "Left face x", "Thickness"]]
               + [[p["name"], p["between"], p["x"], p["thickness"]] for p in spec["partitions"]]
               if spec["partitions"] else [["Partition"], ["none"]],
               [30 * mm, 40 * mm, 35 * mm, CONTENT_W - 105 * mm] if spec["partitions"] else [CONTENT_W], s),
        Spacer(1, 4 * mm),
        _p(f"Doors: {spec['door_type']}", s["h2"]),
    ]
    if spec["doors"]:
        story.append(_table([["Door", "Covers", "Hinge side", "Finish"]]
                            + [[d["name"], d["covers"], d["hinge"], d["finish"]] for d in spec["doors"]],
                            [20 * mm, 45 * mm, 25 * mm, CONTENT_W - 90 * mm], s))
    story += [Spacer(1, 3 * mm), _p(NOT_IN_DESIGN, s["muted"])]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN,
                            bottomMargin=20 * mm, title="BanAI wardrobe specification", author="BanAI",
                            subject=DISCLAIMER)
    doc.reference = reference
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
