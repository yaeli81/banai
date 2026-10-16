"""Function tools offered to the LLM. The `ops` schema is generated from the domain op union,
so the model sees exactly the protocol the engine accepts (domain/ops.py is the single source)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import TypeAdapter

from app.domain.ops import MAX_OPS, Op

PROPOSE = "propose_changes"
CLARIFY = "ask_clarification"
# The chat bubble fits about 105 characters in three lines. The model is asked for <= 90;
# the server enforces MAX_REPLY_CHARS (orchestrator.fit_reply), so a reply never exceeds three lines.
REPLY_TARGET_CHARS = 90
MAX_REPLY_CHARS = 105
MAX_SUMMARY_CHARS = MAX_REPLY_CHARS
MAX_QUESTION_CHARS = MAX_REPLY_CHARS

# Pydantic-only keys that are not JSON Schema (or are noise for the model).
_RENAMES = {"ge": "minimum", "le": "maximum"}
_DROPPED = {"title", "discriminator"}


def _clean(node: object) -> object:
    if isinstance(node, dict):
        return {_RENAMES.get(k, k): _clean(v) for k, v in node.items() if k not in _DROPPED}
    if isinstance(node, list):
        return [_clean(v) for v in node]
    return node


@lru_cache
def op_schema() -> dict:
    return _clean(TypeAdapter(Op).json_schema(by_alias=True))


@lru_cache
def _tools_cached() -> tuple:
    schema = op_schema()
    defs = schema.pop("$defs")
    propose = {
        "type": "function",
        "function": {
            "name": PROPOSE,
            "description": (
                "Propose changes to the current wardrobe as an ordered list of ops. "
                "Nothing is applied until the customer confirms."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "maxLength": MAX_SUMMARY_CHARS,
                        "description": f"ONE short sentence (max {REPLY_TARGET_CHARS} characters) for the customer.",
                    },
                    "ops": {"type": "array", "minItems": 1, "maxItems": MAX_OPS, "items": schema},
                },
                "required": ["summary", "ops"],
                "additionalProperties": False,
                "$defs": defs,
            },
        },
    }
    clarify = {
        "type": "function",
        "function": {
            "name": CLARIFY,
            "description": "Ask the customer one short question when the request is ambiguous or not possible.",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string", "maxLength": MAX_QUESTION_CHARS,
                                            "description": f"ONE short question (max {REPLY_TARGET_CHARS} characters)."}},
                "required": ["question"],
                "additionalProperties": False,
            },
        },
    }
    return (propose, clarify)


def tools() -> list[dict]:
    return list(_tools_cached())
