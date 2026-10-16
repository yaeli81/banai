import json

import pytest

from app.agent.llm import LlmReply, ToolCall
from app.domain.catalog import load_catalog
from app.domain.defaults import basic_wardrobe

SIGNING_KEY = "test-signing-key"


class ScriptedLlm:
    """Returns pre-scripted replies in order and records every conversation it was given."""

    def __init__(self, *replies: LlmReply) -> None:
        self.replies = list(replies)
        self.calls: list[list[dict]] = []

    def complete(self, messages, tools):
        self.calls.append([dict(m) for m in messages])
        return self.replies.pop(0)


def tool(name: str, arguments: dict | str, call_id: str = "call_1") -> LlmReply:
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return LlmReply(content=None, tool_calls=[ToolCall(call_id, name, raw)])


def propose(ops: list, summary: str = "Wider wardrobe.", call_id: str = "call_1") -> LlmReply:
    return tool("propose_changes", {"summary": summary, "ops": ops}, call_id)


@pytest.fixture
def design() -> dict:
    return basic_wardrobe()


@pytest.fixture
def catalog() -> dict:
    return load_catalog()
