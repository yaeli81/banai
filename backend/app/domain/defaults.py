"""Configurable prototype defaults.

ASSUMPTION: every value in this module is a configurable prototype default for
rendering safety and convenience, NOT an approved business or manufacturing
rule. Mirrored in frontend/src/domain/defaults.js.
"""

# (min, max) inclusive, in millimetres unless noted.
LIMITS: dict[str, tuple[int, int]] = {
    "width": (300, 6000),
    "height": (300, 3500),
    "depth": (200, 1200),
    "panelThickness": (5, 50),
    "partitionThickness": (5, 50),
    "compartmentWidth": (50, 6000),
    "shelfThickness": (5, 60),
    "drawerHeight": (50, 1000),
    "compartmentCount": (1, 20),
    "slidingDoorCount": (1, 6),
}

DEFAULT_PANEL_THICKNESS = 18
DEFAULT_SHELF_THICKNESS = 18
DEFAULT_SLIDING_DOOR_COUNT = 2


def default_appearance() -> dict:
    return {
        "material": {"catalogId": "melamine"},
        "color": {"catalogId": "white"},
        "finish": {"catalogId": "matte"},
    }


BASIC_WARDROBE_OPS: list[dict] = [
    {"op": "create_wardrobe", "width": 2000, "height": 2400, "depth": 600, "compartmentCount": 3,
     "compartmentIds": ["cmp_left", "cmp_middle", "cmp_right"], "partitionIds": ["prt_1", "prt_2"]},
    {"op": "add_shelf", "compartmentId": "cmp_left", "y": 400, "id": "shf_l1"},
    {"op": "add_shelf", "compartmentId": "cmp_left", "y": 800, "id": "shf_l2"},
    {"op": "add_shelf", "compartmentId": "cmp_left", "y": 1200, "id": "shf_l3"},
    {"op": "add_shelf", "compartmentId": "cmp_left", "y": 1600, "id": "shf_l4"},
    {"op": "add_shelf", "compartmentId": "cmp_middle", "y": 2000, "id": "shf_m1"},
    {"op": "add_rail", "compartmentId": "cmp_middle", "y": 1900, "id": "rail_m1"},
    {"op": "add_shelf", "compartmentId": "cmp_right", "y": 800, "id": "shf_r1"},
    {"op": "add_shelf", "compartmentId": "cmp_right", "y": 1400, "id": "shf_r2"},
    {"op": "add_drawer", "compartmentId": "cmp_right", "y": 0, "height": 200, "id": "drw_r1"},
    {"op": "add_drawer", "compartmentId": "cmp_right", "y": 200, "height": 200, "id": "drw_r2"},
    {"op": "configure_doors", "type": "hinged", "ids": ["dr_left", "dr_middle", "dr_right"]},
]


# ASSUMPTION: the templates below are configurable starting points (sizes, layout, colours),
# not business or manufacturing rules. Mirrored in frontend/src/domain/presets.js.
KIDS_WARDROBE_OPS: list[dict] = [
    {"op": "create_wardrobe", "width": 1500, "height": 1800, "depth": 550, "compartmentCount": 2,
     "compartmentIds": ["cmp_kids_hang", "cmp_kids_store"], "partitionIds": ["prt_kids"]},
    {"op": "add_rail", "compartmentId": "cmp_kids_hang", "y": 1100, "id": "rail_kids"},  # within a child's reach
    {"op": "add_shelf", "compartmentId": "cmp_kids_hang", "y": 1300, "id": "shf_kids_top"},
    {"op": "add_drawer", "compartmentId": "cmp_kids_store", "y": 0, "height": 180, "id": "drw_kids1"},
    {"op": "add_drawer", "compartmentId": "cmp_kids_store", "y": 180, "height": 180, "id": "drw_kids2"},
    {"op": "add_drawer", "compartmentId": "cmp_kids_store", "y": 360, "height": 180, "id": "drw_kids3"},
    {"op": "add_shelf", "compartmentId": "cmp_kids_store", "y": 900, "id": "shf_kids1"},
    {"op": "add_shelf", "compartmentId": "cmp_kids_store", "y": 1300, "id": "shf_kids2"},
    {"op": "configure_doors", "type": "hinged", "ids": ["dr_kids_left", "dr_kids_right"]},
    {"op": "set_material", "target": "doors", "color": {"catalogId": "sage_green"}},
]

SLIDING_WARDROBE_OPS: list[dict] = [
    {"op": "create_wardrobe", "width": 2400, "height": 2400, "depth": 650, "compartmentCount": 2,
     "compartmentIds": ["cmp_his", "cmp_hers"], "partitionIds": ["prt_couple"]},
    {"op": "add_rail", "compartmentId": "cmp_his", "y": 1900, "id": "rail_his"},
    {"op": "add_shelf", "compartmentId": "cmp_his", "y": 2050, "id": "shf_his"},
    {"op": "add_drawer", "compartmentId": "cmp_hers", "y": 0, "height": 200, "id": "drw_hers1"},
    {"op": "add_drawer", "compartmentId": "cmp_hers", "y": 200, "height": 200, "id": "drw_hers2"},
    {"op": "add_rail", "compartmentId": "cmp_hers", "y": 1900, "id": "rail_hers"},
    {"op": "add_shelf", "compartmentId": "cmp_hers", "y": 2050, "id": "shf_hers"},
    {"op": "configure_doors", "type": "sliding", "ids": ["dr_slide1", "dr_slide2"]},
]

MINIMAL_WARDROBE_OPS: list[dict] = [
    {"op": "create_wardrobe", "width": 1200, "height": 2200, "depth": 600, "compartmentCount": 2,
     "compartmentIds": ["cmp_min_hang", "cmp_min_shelves"], "partitionIds": ["prt_min"]},
    {"op": "add_rail", "compartmentId": "cmp_min_hang", "y": 1750, "id": "rail_min"},
    {"op": "add_shelf", "compartmentId": "cmp_min_shelves", "y": 500, "id": "shf_min1"},
    {"op": "add_shelf", "compartmentId": "cmp_min_shelves", "y": 1000, "id": "shf_min2"},
    {"op": "add_shelf", "compartmentId": "cmp_min_shelves", "y": 1500, "id": "shf_min3"},
    {"op": "configure_doors", "type": "hinged", "ids": ["dr_min_left", "dr_min_right"]},
    {"op": "set_material", "target": "doors", "color": {"catalogId": "light_grey"}},
]

PRESET_OPS: dict[str, list[dict]] = {
    "basic": BASIC_WARDROBE_OPS,
    "kids": KIDS_WARDROBE_OPS,
    "sliding": SLIDING_WARDROBE_OPS,
    "minimal": MINIMAL_WARDROBE_OPS,
}


def basic_wardrobe() -> dict:
    """The predefined starting wardrobe (entry option 3). Built through the op protocol."""
    from app.domain.apply import apply_ops  # local import: apply depends on this module
    from app.domain.catalog import load_catalog

    return apply_ops(None, BASIC_WARDROBE_OPS, load_catalog())


def preset_design(preset_id: str) -> dict:
    """A starting template built through the op protocol. Raises KeyError on an unknown id."""
    from app.domain.apply import apply_ops  # local import: apply depends on this module
    from app.domain.catalog import load_catalog

    return apply_ops(None, PRESET_OPS[preset_id], load_catalog())
