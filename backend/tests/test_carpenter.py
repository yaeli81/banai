"""Carpenter spec (numbers come from the design only) and the PDF endpoint."""

import base64
import copy
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr
from pypdf import PdfReader

from app.api.carpenter import MAX_IMAGE_SIDE
from app.carpenter.pdf import DISCLAIMER_LINES
from app.carpenter.spec import build_spec
from app.config import Settings, get_settings
from app.domain.apply import apply_ops
from app.domain.catalog import load_catalog
from app.domain.defaults import basic_wardrobe
from app.main import app

FIXTURES = Path(__file__).resolve().parents[2] / "shared" / "fixtures" / "designs"
CATALOG = load_catalog()


def png_data_url(size=(320, 200), color="#dfe6da") -> str:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


IMAGES = {"closed": png_data_url(), "interior": png_data_url(color="#e9e2da")}


@pytest.fixture
def client():
    settings = Settings(_env_file=None, app_env="test", proposal_signing_key=SecretStr("k"),
                        chat_rate_limit_per_minute=1000)
    app.dependency_overrides[get_settings] = lambda: settings
    yield TestClient(app)
    app.dependency_overrides.clear()


def pdf_text(content: bytes) -> list[str]:
    return [page.extract_text() for page in PdfReader(io.BytesIO(content)).pages]


# --- spec: every number is the design's own -------------------------------------------------

def test_spec_matches_the_basic_wardrobe_exactly():
    design = basic_wardrobe()
    spec = build_spec(design, CATALOG)
    assert spec["overall"] == {"width": 2000, "height": 2400, "depth": 600}
    assert spec["interior"] == {"width": 1964, "height": 2364}
    widths = [c["width"] for c in spec["compartments"]]
    assert widths == [c["width"] for c in design["compartments"]]
    assert sum(widths) + sum(p["thickness"] for p in spec["partitions"]) == spec["interior"]["width"]
    # Compartments tile the interior from x = 0 to the interior width, partitions in between.
    assert spec["compartments"][0]["x_from"] == 0 and spec["compartments"][-1]["x_to"] == 1964
    assert [p["x"] for p in spec["partitions"]] == [c["x_to"] for c in spec["compartments"][:-1]]
    right = spec["compartments"][2]["items"]
    assert [(i["kind"], i["y"], i["size"]) for i in right] == [
        ("Drawer", 0, 200), ("Drawer", 200, 200), ("Shelf", 800, 18), ("Shelf", 1400, 18)]
    assert spec["door_type"] == "Hinged" and [d["covers"] for d in spec["doors"]] == ["C1", "C2", "C3"]
    assert spec["finishes"]["carcass"] == "Melamine board · White · Matte"


def test_spec_for_the_two_compartment_fixture():
    design = apply_ops(json.loads((FIXTURES / "two.json").read_text(encoding="utf-8")), [], CATALOG)
    spec = build_spec(design, CATALOG)
    assert spec["panel_thickness"] == 20 and spec["interior"] == {"width": 960, "height": 1960}
    assert spec["partitions"] == [{"name": "P1", "id": "prt_ab", "between": "C1 | C2", "x": 470, "thickness": 20}]
    assert [d["hinge"] for d in spec["doors"]] == ["left", "right"]
    assert spec["counts"] == {"shelves": 1, "drawers": 1, "rails": 1}


def test_spec_shows_custom_finishes_and_sliding_doors():
    design = apply_ops(basic_wardrobe(), [
        {"op": "configure_doors", "type": "sliding", "count": 2},
        {"op": "set_material", "target": "shf_l1", "color": {"custom": True, "name": "Sage", "hex": "#9CAF88"}},
    ], CATALOG)
    spec = build_spec(design, CATALOG)
    assert [d["covers"] for d in spec["doors"]] == ["full width (sliding)"] * 2
    assert spec["compartments"][0]["items"][0]["finish"] == "Melamine board · Sage (custom, #9CAF88) · Matte"


# --- PDF endpoint -------------------------------------------------------------------------

def test_pdf_contains_every_dimension_and_the_disclaimer_on_every_page(client):
    design = basic_wardrobe()
    response = client.post("/api/carpenter/pdf", json={"design": design, "images": IMAGES})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith('attachment; filename="banai-wardrobe-')
    assert response.content.startswith(b"%PDF")
    pages = pdf_text(response.content)
    assert len(pages) == 3
    for page in pages:
        flat = " ".join(page.split())
        assert all(" ".join(line.split()) in flat for line in DISCLAIMER_LINES)
    text = " ".join(pages)
    assert "2000 × 2400 × 600" in text and "1964 × 2364" in text
    for compartment in design["compartments"]:
        assert str(compartment["width"]) in text
        for item in compartment["shelves"] + compartment["drawers"] + compartment["rails"]:
            assert str(item["y"]) in text
    assert "manufacturable" not in text.lower() and "ready for production" not in text.lower()


def test_hebrew_custom_names_render(client):
    design = apply_ops(basic_wardrobe(), [{"op": "set_material", "target": "doors",
                                           "color": {"custom": True, "name": "ירוק מרווה", "hex": "#9CAF88"}}], CATALOG)
    response = client.post("/api/carpenter/pdf", json={"design": design, "images": IMAGES})
    assert response.status_code == 200
    assert "מרווה" in " ".join(pdf_text(response.content)) or "הוורמ" in " ".join(pdf_text(response.content))


def test_invalid_design_is_422(client):
    design = basic_wardrobe()
    design["dimensions"]["width"] = 5
    response = client.post("/api/carpenter/pdf", json={"design": design, "images": IMAGES})
    assert response.status_code == 422 and response.json()["success"] is False


@pytest.mark.parametrize("bad", [
    "data:image/jpeg;base64,AAAA",
    "data:image/png;base64,not-base64!!",
    "data:image/png;base64," + base64.b64encode(b"GIF89a fake").decode(),
    "https://example.com/x.png",
])
def test_bad_images_are_422(client, bad):
    response = client.post("/api/carpenter/pdf", json={"design": basic_wardrobe(), "images": {**IMAGES, "closed": bad}})
    assert response.status_code == 422 and response.json()["error"]["code"] == "INVALID_IMAGE"


def test_huge_pixel_image_is_rejected(client):
    huge = png_data_url(size=(MAX_IMAGE_SIDE + 1, 2))
    response = client.post("/api/carpenter/pdf", json={"design": basic_wardrobe(), "images": {**IMAGES, "interior": huge}})
    assert response.status_code == 422


def test_missing_image_or_extra_field_is_422(client):
    assert client.post("/api/carpenter/pdf", json={"design": basic_wardrobe(), "images": {"closed": IMAGES["closed"]}}).status_code == 422
    assert client.post("/api/carpenter/pdf", json={"design": basic_wardrobe(), "images": IMAGES, "x": 1}).status_code == 422


def test_body_over_the_route_cap_is_413(client):
    response = client.post("/api/carpenter/pdf", content=b"x" * (10 * 1024 * 1024), headers={"content-type": "application/json"})
    assert response.status_code == 413


def test_the_request_design_is_not_mutated(client):
    design = basic_wardrobe()
    before = copy.deepcopy(design)
    client.post("/api/carpenter/pdf", json={"design": design, "images": IMAGES})
    assert design == before
