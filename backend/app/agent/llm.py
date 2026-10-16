"""LLM clients behind one small interface, so the orchestrator never depends on a vendor SDK.

`OpenAiLlm` is the real client. `FakeLlm` is a deterministic, rule-based stand-in used by
Playwright (AGENT_MODE=fake, only allowed when APP_ENV is test/e2e): it understands a few
phrases such as "240 cm wide" or "sliding doors" and never calls the network.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Protocol


class LlmError(Exception):
    """The LLM could not be reached or answered unusably. The message is safe to log, not to show."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON text, parsed and validated by the orchestrator


@dataclass(frozen=True)
class LlmReply:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)

    def as_message(self) -> dict:
        """The assistant message to append to the conversation before tool results."""
        message: dict = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            message["tool_calls"] = [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
                for c in self.tool_calls
            ]
        return message


class LlmClient(Protocol):
    def complete(self, messages: list[dict], tools: list[dict]) -> LlmReply: ...


class OpenAiLlm:
    def __init__(self, api_key: str, model: str, timeout_seconds: float) -> None:
        from openai import OpenAI  # imported lazily: tests never need the SDK client

        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=1)
        self._model = model

    def complete(self, messages: list[dict], tools: list[dict]) -> LlmReply:
        import openai

        try:
            response = self._client.chat.completions.create(
                model=self._model, messages=messages, tools=tools, tool_choice="required",
                parallel_tool_calls=False,
            )
        except openai.OpenAIError as error:
            raise LlmError(type(error).__name__) from error
        if not response.choices:
            raise LlmError("empty response")
        message = response.choices[0].message
        calls = [
            ToolCall(id=c.id, name=c.function.name, arguments=c.function.arguments or "")
            for c in (message.tool_calls or [])
            if getattr(c, "function", None) is not None
        ]
        return LlmReply(content=message.content, tool_calls=calls)


# "<number> <unit> ... wide" without crossing another number ("2.6 m wide and 250 cm tall").
_WIDTH = re.compile(r"(\d+(?:\.\d+)?)\s*(cm|mm|m)\b[^.\d]*?\bwide", re.IGNORECASE)
_HEIGHT = re.compile(r"(\d+(?:\.\d+)?)\s*(cm|mm|m)\b[^.\d]*?\b(tall|high)", re.IGNORECASE)
_TO_MM = {"mm": 1, "cm": 10, "m": 1000}


def _mm(value: str, unit: str) -> int:
    return round(float(value) * _TO_MM[unit.lower()])


class FakeLlm:
    """Rule-based fake for E2E. Reads the latest customer message only."""

    def complete(self, messages: list[dict], tools: list[dict]) -> LlmReply:
        if messages and messages[-1]["role"] == "tool":
            # A tool result means the previous proposal failed validation: ask instead of retrying.
            return self._call("ask_clarification", {"question": "Could you describe that change differently?"})
        text = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        ops: list[dict] = []
        dims: dict = {}
        if match := _WIDTH.search(text):
            dims["width"] = _mm(*match.groups())
        if match := _HEIGHT.search(text):
            dims["height"] = _mm(*match.groups()[:2])
        if dims:
            ops.append({"op": "update_dimensions", **dims})
        lowered = text.lower()
        if "sliding" in lowered:
            ops.append({"op": "configure_doors", "type": "sliding", "count": 2})
        elif "no doors" in lowered:
            ops.append({"op": "configure_doors", "type": "none"})
        elif "hinged" in lowered:
            ops.append({"op": "configure_doors", "type": "hinged"})
        if not ops:
            return self._call("ask_clarification", {"question": "What size or doors would you like?"})
        return self._call("propose_changes", {"summary": "Here is a proposal based on your request.", "ops": ops})

    @staticmethod
    def _call(name: str, arguments: dict) -> LlmReply:
        return LlmReply(content=None, tool_calls=[ToolCall(f"call_{uuid.uuid4().hex[:8]}", name, json.dumps(arguments))])
