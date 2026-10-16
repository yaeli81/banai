"""Deterministic, server-written change list for the proposal card.

The card shows what the ops will do, phrased by the server from the validated ops,
not LLM prose. Ids are mapped to readable names ("Compartment 2") from the design.
"""

from __future__ import annotations

from app.domain import ops as op_types
from app.domain.defaults import DEFAULT_SLIDING_DOOR_COUNT

DOOR_TYPES = {"hinged": "Hinged doors", "sliding": "Sliding doors", "none": "No doors"}
ITEM_NAMES = {"shf": "Shelf", "drw": "Drawer", "rail": "Hanging rail", "dr": "Door", "prt": "Partition", "cmp": "Compartment"}


def cm(mm: int) -> str:
    value = mm / 10
    return f"{value:g} cm"


def _compartment_label(design: dict, compartment_id: str) -> str:
    for index, compartment in enumerate(design["compartments"]):
        if compartment["id"] == compartment_id:
            return f"Compartment {index + 1}"
    return "New compartment"


def _ref_name(ref, catalog: dict, section: str) -> str:
    if ref is None:
        return ""
    if getattr(ref, "custom", False):
        return ref.name
    names = {entry["id"]: entry["name"] for entry in catalog[section]}
    return names.get(ref.catalog_id, ref.catalog_id)


def _target_label(design: dict, target: str) -> str:
    if target == "carcass":
        return "Carcass & interior"
    if target == "doors":
        return "Doors"
    prefix = target.split("_", 1)[0]
    return ITEM_NAMES.get(prefix, "Component")


def describe_op(op, before: dict, catalog: dict) -> dict:
    d = before["dimensions"]
    match op:
        case op_types.CreateWardrobe():
            return {"title": "New wardrobe",
                    "detail": f"{cm(op.width)} × {cm(op.height)} × {cm(op.depth)}, {op.compartment_count} compartments"}
        case op_types.UpdateDimensions():
            parts = [f"{label} {cm(d[key])} → {cm(new)}"
                     for label, key, new in (("Width", "width", op.width), ("Height", "height", op.height),
                                             ("Depth", "depth", op.depth)) if new is not None]
            return {"title": "Dimensions", "detail": ", ".join(parts)}
        case op_types.ConfigureDoors():
            if op.type == "none":
                return {"title": DOOR_TYPES[op.type], "detail": "Open front"}
            # Same defaults as the engine: sliding -> 2 doors, hinged -> one per compartment.
            default = DEFAULT_SLIDING_DOOR_COUNT if op.type == "sliding" else len(before["compartments"])
            count = op.count or (len(op.ids) if op.ids else None) or (len(op.doors) if op.doors else None) or default
            return {"title": DOOR_TYPES[op.type], "detail": f"{count} door{'s' if count != 1 else ''}"}
        case op_types.AddCompartment():
            return {"title": "Add compartment", "detail": f"{cm(op.width)} wide at position {op.position + 1}"}
        case op_types.ModifyCompartment():
            return {"title": _compartment_label(before, op.compartment_id), "detail": f"Width → {cm(op.width)}"}
        case op_types.AddPartition():
            return {"title": "Add partition",
                    "detail": f"{_compartment_label(before, op.compartment_id)}, {cm(op.offset)} from its left side"}
        case op_types.ModifyPartition():
            detail = f"Position → {cm(op.position)}" if op.position is not None else f"Thickness → {op.thickness} mm"
            return {"title": "Move partition", "detail": detail}
        case op_types.AddShelf():
            return {"title": "Add shelf", "detail": f"{_compartment_label(before, op.compartment_id)}, at {cm(op.y)}"}
        case op_types.AddDrawer():
            return {"title": "Add drawer",
                    "detail": f"{_compartment_label(before, op.compartment_id)}, at {cm(op.y)}, {cm(op.height)} high"}
        case op_types.AddRail():
            return {"title": "Add hanging rail", "detail": f"{_compartment_label(before, op.compartment_id)}, at {cm(op.y)}"}
        case op_types.ModifyShelf() | op_types.ModifyDrawer() | op_types.ModifyRail():
            name = ITEM_NAMES[op.id.split("_", 1)[0]]
            y = getattr(op, "y", None)
            return {"title": f"Move {name.lower()}", "detail": f"to {cm(y)}" if y is not None else "Resize"}
        case op_types.SetMaterial():
            if op.clear:
                return {"title": _target_label(before, op.target), "detail": "Use the default finish"}
            parts = [_ref_name(op.material, catalog, "materials"), _ref_name(op.color, catalog, "colors"),
                     _ref_name(op.finish, catalog, "finishes")]
            return {"title": _target_label(before, op.target), "detail": ", ".join(p for p in parts if p)}
        case op_types.RemoveComponent():
            name = ITEM_NAMES.get(op.id.split("_", 1)[0], "Component")
            if name == "Compartment":
                name = _compartment_label(before, op.id)
            return {"title": "Remove", "detail": name}
    return {"title": "Change", "detail": op.op}


def describe_ops(parsed_ops: list, before: dict, catalog: dict) -> list[dict]:
    return [describe_op(op, before, catalog) for op in parsed_ops]
