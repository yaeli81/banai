import pytest

from app.domain.defaults import PRESET_OPS, basic_wardrobe, preset_design
from app.domain.validation import validate_design

from .conftest import load_design

TEMPLATES = ["kids", "sliding", "minimal"]


@pytest.mark.parametrize("preset_id", TEMPLATES)
def test_template_is_valid_and_matches_shared_fixture(preset_id, catalog):
    design = preset_design(preset_id)
    assert validate_design(design, catalog) == []
    assert design == load_design(f"preset_{preset_id}")


def test_basic_template_is_the_basic_wardrobe():
    assert preset_design("basic") == basic_wardrobe()


def test_template_ids_match_the_frontend():
    assert set(PRESET_OPS) == {"basic", *TEMPLATES}


def test_unknown_template_raises():
    with pytest.raises(KeyError):
        preset_design("castle")
