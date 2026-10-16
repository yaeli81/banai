"""The carpenter spec: every number comes straight from the canonical design (integer mm).

Nothing is computed beyond positions the design already implies (x-ranges from widths); no cut
list, joinery or tolerances are invented. Interior coordinates follow `domain/geometry.py`:
x = 0 at the inner face of the left side panel, y = 0 at the top face of the bottom panel.
"""

from __future__ import annotations

from app.domain.catalog import SECTIONS
from app.domain.geometry import compartment_x_ranges, interior_height, interior_width, partition_left_edge

DOOR_TYPES = {"hinged": "Hinged", "sliding": "Sliding", "none": "No doors"}


def describe_appearance(appearance: dict | None, catalog: dict) -> str | None:
    """'Melamine board · White · Matte'; custom entries show their name and hex."""
    if appearance is None:
        return None
    parts = []
    for field, section in SECTIONS.items():
        ref = appearance[field]
        if ref.get("custom"):
            parts.append(f"{ref['name']} (custom{', ' + ref['hex'] if ref.get('hex') else ''})")
        else:
            names = {entry["id"]: entry["name"] for entry in catalog[section]}
            parts.append(names.get(ref["catalogId"], ref["catalogId"]))
    return " · ".join(parts)


def build_spec(design: dict, catalog: dict) -> dict:
    panel = design["carcass"]["panelThickness"]
    carcass_finish = describe_appearance(design["carcass"]["appearance"], catalog)
    door_finish = describe_appearance(design["doors"]["appearance"], catalog)
    ranges = compartment_x_ranges(design)
    names = {c["id"]: f"C{i + 1}" for i, c in enumerate(design["compartments"])}

    compartments = []
    for index, (compartment, (x0, x1)) in enumerate(zip(design["compartments"], ranges)):
        items = [
            {"kind": "Shelf", "id": s["id"], "y": s["y"], "size": s["thickness"], "size_label": "thickness",
             "finish": describe_appearance(s["appearance"], catalog)}
            for s in compartment["shelves"]
        ] + [
            {"kind": "Drawer", "id": d["id"], "y": d["y"], "size": d["height"], "size_label": "height",
             "finish": describe_appearance(d["appearance"], catalog)}
            for d in compartment["drawers"]
        ] + [
            {"kind": "Hanging rail", "id": r["id"], "y": r["y"], "size": None, "size_label": "", "finish": None}
            for r in compartment["rails"]
        ]
        items.sort(key=lambda item: (item["y"], item["kind"]))
        compartments.append({"name": f"C{index + 1}", "id": compartment["id"], "x_from": x0, "x_to": x1,
                             "width": compartment["width"], "items": items})

    partitions = [
        {"name": f"P{j + 1}", "id": p["id"], "between": f"C{j + 1} | C{j + 2}",
         "x": partition_left_edge(design, j), "thickness": p["thickness"]}
        for j, p in enumerate(design["partitions"])
    ]
    doors = [
        {"name": f"D{k + 1}", "id": d["id"],
         "covers": ", ".join(names[c] for c in d["compartmentIds"]) or "full width (sliding)",
         "hinge": d["hingeSide"] or "—", "finish": describe_appearance(d["appearance"], catalog) or door_finish}
        for k, d in enumerate(design["doors"]["items"])
    ]
    return {
        "overall": dict(design["dimensions"]),
        "panel_thickness": panel,
        # No interior depth: back panel, door thickness, gaps and hardware are not part of the design.
        "interior": {"width": interior_width(design), "height": interior_height(design)},
        "compartments": compartments,
        "partitions": partitions,
        "door_type": DOOR_TYPES[design["doors"]["type"]],
        "doors": doors,
        "finishes": {"carcass": carcass_finish, "doors": door_finish},
        "counts": {
            "shelves": sum(len(c["shelves"]) for c in design["compartments"]),
            "drawers": sum(len(c["drawers"]) for c in design["compartments"]),
            "rails": sum(len(c["rails"]) for c in design["compartments"]),
        },
    }
