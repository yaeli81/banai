import json

from pydantic import TypeAdapter

from app.agent.describe import describe_ops
from app.agent.llm import FakeLlm
from app.agent.tools import op_schema, tools
from app.api.rate_limit import RateLimiter
from app.domain.ops import Op, parse_ops
from app.services import signing


def test_tool_schema_covers_every_op_and_is_plain_json_schema():
    names = {branch["$ref"].rsplit("/", 1)[1] for branch in op_schema()["oneOf"]}
    expected = {branch["$ref"].rsplit("/", 1)[1] for branch in TypeAdapter(Op).json_schema()["oneOf"]}
    assert names == expected and len(names) == 15
    text = json.dumps(tools())
    assert '"ge"' not in text and '"le"' not in text and '"title"' not in text


def test_design_hash_ignores_key_order():
    assert signing.design_hash({"a": 1, "b": [1, 2]}) == signing.design_hash({"b": [1, 2], "a": 1})


def test_signature_covers_every_field():
    sig = signing.sign("k", "prop_1", [{"op": "x"}], 2, "h")
    assert signing.verify("k", sig, "prop_1", [{"op": "x"}], 2, "h")
    assert not signing.verify("other", sig, "prop_1", [{"op": "x"}], 2, "h")
    assert not signing.verify("k", sig, "prop_2", [{"op": "x"}], 2, "h")
    assert not signing.verify("k", sig, "prop_1", [{"op": "y"}], 2, "h")
    assert not signing.verify("k", sig, "prop_1", [{"op": "x"}], 3, "h")
    assert not signing.verify("k", sig, "prop_1", [{"op": "x"}], 2, "g")


def test_describe_uses_readable_names(design, catalog):
    ops = parse_ops([
        {"op": "set_material", "target": "doors", "color": {"catalogId": "walnut"}},
        {"op": "remove_component", "id": "cmp_middle"},
        {"op": "configure_doors", "type": "none"},
        {"op": "add_drawer", "compartmentId": "cmp_right", "y": 400, "height": 150},
    ])
    assert describe_ops(ops, design, catalog) == [
        {"title": "Doors", "detail": "Walnut"},
        {"title": "Remove", "detail": "Compartment 2"},
        {"title": "No doors", "detail": "Open front"},
        {"title": "Add drawer", "detail": "Compartment 3, at 40 cm, 15 cm high"},
    ]


def test_fake_llm_understands_size_and_doors():
    reply = FakeLlm().complete([{"role": "user", "content": "2.6 m wide and 250 cm tall with hinged doors"}], [])
    args = json.loads(reply.tool_calls[0].arguments)
    assert args["ops"] == [{"op": "update_dimensions", "width": 2600, "height": 2500},
                           {"op": "configure_doors", "type": "hinged"}]


def test_fake_llm_asks_when_it_does_not_understand():
    reply = FakeLlm().complete([{"role": "user", "content": "make it nice"}], [])
    assert reply.tool_calls[0].name == "ask_clarification"


def test_rate_limiter_window():
    now = [0.0]
    limiter = RateLimiter(2, window_seconds=60, clock=lambda: now[0])
    assert limiter.allow("a") and limiter.allow("a") and not limiter.allow("a")
    assert limiter.allow("b")
    now[0] = 61
    assert limiter.allow("a")


def test_describe_door_counts_follow_engine_defaults(design, catalog):
    ops = parse_ops([{"op": "configure_doors", "type": "sliding"}, {"op": "configure_doors", "type": "hinged"},
                     {"op": "configure_doors", "type": "sliding", "count": 3}])
    assert [c["detail"] for c in describe_ops(ops, design, catalog)] == ["2 doors", "3 doors", "3 doors"]
