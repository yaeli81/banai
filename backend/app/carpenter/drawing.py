"""To-scale front elevation (doors removed) with dimension lines, as a reportlab Drawing."""

from __future__ import annotations

from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.lib import colors

from app.carpenter.text import FONT, FONT_BOLD

PANEL = colors.HexColor("#d9cfc4")
SHELF = colors.HexColor("#b9a796")
DRAWER = colors.HexColor("#efe7de")
INK = colors.HexColor("#2b211c")
DIM = colors.HexColor("#b4532a")
MUTED = colors.HexColor("#6b5e57")

MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM = 46, 16, 34, 42  # points, room for dimensions


def _dim_h(d: Drawing, x0: float, x1: float, y: float, label: str, tick: float = 4) -> None:
    d.add(Line(x0, y, x1, y, strokeColor=DIM, strokeWidth=0.6))
    for x in (x0, x1):
        d.add(Line(x, y - tick, x, y + tick, strokeColor=DIM, strokeWidth=0.6))
    d.add(String((x0 + x1) / 2, y + 3, label, fontName=FONT, fontSize=7, fillColor=DIM, textAnchor="middle"))


def _dim_v(d: Drawing, x: float, y0: float, y1: float, label: str, tick: float = 4) -> None:
    d.add(Line(x, y0, x, y1, strokeColor=DIM, strokeWidth=0.6))
    for y in (y0, y1):
        d.add(Line(x - tick, y, x + tick, y, strokeColor=DIM, strokeWidth=0.6))
    label_shape = String(0, 0, label, fontName=FONT, fontSize=7, fillColor=DIM, textAnchor="middle")
    # Rotated label: reportlab shapes rotate via a group transform.
    from reportlab.graphics.shapes import Group

    group = Group(label_shape)
    group.transform = (0, 1, -1, 0, x - 4, (y0 + y1) / 2)
    d.add(group)


def front_elevation(design: dict, spec: dict, max_width: float, max_height: float) -> Drawing:
    W, H = design["dimensions"]["width"], design["dimensions"]["height"]
    panel = design["carcass"]["panelThickness"]
    usable_w = max_width - MARGIN_LEFT - MARGIN_RIGHT
    usable_h = max_height - MARGIN_TOP - MARGIN_BOTTOM
    scale = min(usable_w / W, usable_h / H)  # points per mm
    d = Drawing(MARGIN_LEFT + W * scale + MARGIN_RIGHT, MARGIN_BOTTOM + H * scale + MARGIN_TOP)

    def X(mm: float) -> float:
        return MARGIN_LEFT + mm * scale

    def Y(mm: float) -> float:
        return MARGIN_BOTTOM + mm * scale

    def rect(x, y, w, h, fill, stroke=INK, width=0.4):
        d.add(Rect(X(x), Y(y), w * scale, h * scale, fillColor=fill, strokeColor=stroke, strokeWidth=width))

    # Carcass: sides, bottom, top (outer coordinates, mm from the outer bottom-left corner).
    rect(0, 0, W, H, colors.white, width=0.8)
    rect(0, 0, panel, H, PANEL)
    rect(W - panel, 0, panel, H, PANEL)
    rect(panel, 0, W - 2 * panel, panel, PANEL)
    rect(panel, H - panel, W - 2 * panel, panel, PANEL)
    inner_h = H - 2 * panel

    for partition in spec["partitions"]:
        rect(panel + partition["x"], panel, partition["thickness"], inner_h, PANEL)

    for compartment in spec["compartments"]:
        x0, width = panel + compartment["x_from"], compartment["width"]
        for item in compartment["items"]:
            y = panel + item["y"]
            if item["kind"] == "Shelf":
                rect(x0, y, width, item["size"], SHELF)
            elif item["kind"] == "Drawer":
                rect(x0, y, width, item["size"], DRAWER, width=0.5)
                handle_y = Y(y + item["size"] / 2)
                d.add(Line(X(x0 + width * 0.4), handle_y, X(x0 + width * 0.6), handle_y, strokeColor=INK, strokeWidth=1))
            else:
                d.add(Line(X(x0), Y(y), X(x0 + width), Y(y), strokeColor=INK, strokeWidth=1.4))
                for end in (x0, x0 + width):
                    d.add(Circle(X(end), Y(y), 1.4, fillColor=INK, strokeColor=INK))
            # The y of every item, at the left inside edge of its compartment.
            d.add(String(X(x0) + 2, Y(y) + 2, f"{item['y']}", fontName=FONT, fontSize=5.5, fillColor=MUTED))
        # Compartment name, centred near the top of the interior.
        d.add(String(X(x0 + width / 2), Y(H - panel) - 9, compartment["name"], fontName=FONT_BOLD, fontSize=7,
                     fillColor=MUTED, textAnchor="middle"))

    # Dimension lines: overall width (top), compartment widths (bottom), overall + interior height (left).
    _dim_h(d, X(0), X(W), Y(H) + 14, f"{W}")
    for compartment in spec["compartments"]:
        x0 = panel + compartment["x_from"]
        _dim_h(d, X(x0), X(x0 + compartment["width"]), Y(0) - 14, f"{compartment['width']}", tick=3)
    _dim_v(d, X(0) - 30, Y(0), Y(H), f"{H}")
    _dim_v(d, X(0) - 14, Y(panel), Y(H - panel), f"{inner_h}", tick=3)
    d.add(String(X(0), Y(0) - 34, "Front view, doors removed. All dimensions in mm. Item labels = height (y) above "
                 "the top of the bottom panel.", fontName=FONT, fontSize=6.5, fillColor=MUTED))
    return d
