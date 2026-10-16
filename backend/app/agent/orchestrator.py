"""One agent turn: customer messages + committed design -> reply and an optional signed proposal.

The agent never applies anything. Tool arguments are untrusted: they are parsed with the
domain op models and dry-run on a copy of the design. Invalid ops are sent back to the model
to repair (at most MAX_REPAIRS times); after that the customer gets a clarification instead.
"""

from __future__ import annotations

import json
import re
import uuid

from app.agent import prompts
from app.agent.describe import describe_ops
from app.agent.llm import LlmClient, LlmError
from app.agent.tools import CLARIFY, MAX_QUESTION_CHARS, MAX_SUMMARY_CHARS, PROPOSE, tools
from app.domain.apply import apply_ops
from app.domain.errors import DomainError
from app.domain.ops import parse_ops
from app.services import signing

MAX_REPAIRS = 2
FALLBACK_REPLY = "I couldn't turn that into a valid change. Could you describe it a little differently?"
DEFAULT_SUMMARY = "Here is a proposal based on your request."

# Control, zero-width, bidi-override and Unicode tag characters never reach the UI.
_UNSAFE_TEXT = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f​-‍  ‪-‮⁦-⁩﻿\U000e0000-\U000e007f]")


_SENTENCE_END = re.compile(r"(?<=[.!?。])\s+")
_WHITESPACE = re.compile(r"\s+")


def fit_reply(text: str, limit: int) -> str:
    """Keep whole sentences that fit in `limit`; otherwise cut the first one at a word, with an ellipsis."""
    if len(text) <= limit:
        return text
    kept = ""
    for sentence in _SENTENCE_END.split(text):
        candidate = f"{kept} {sentence}".strip()
        if len(candidate) > limit:
            break
        kept = candidate
    if kept:
        return kept
    cut = text[: limit - 1]
    if " " in cut:
        cut = cut[: cut.rindex(" ")]
    return cut.rstrip(" ,;:-") + "…"


def clean_text(value: object, limit: int) -> str:
    """Strip unsafe characters, collapse whitespace (the bubble shows one paragraph), fit to `limit`."""
    if not isinstance(value, str):
        return ""
    text = _WHITESPACE.sub(" ", _UNSAFE_TEXT.sub("", value)).strip()
    return fit_reply(text, limit)


class _Rejected(Exception):
    """The model's tool call could not be used; the message is fed back to the model."""


def run_turn(
    *, messages: list[dict], design: dict, revision: int, catalog: dict, llm: LlmClient, signing_key: str
) -> dict:
    conversation = [{"role": "system", "content": prompts.SYSTEM_PROMPT}, prompts.context_message(design, catalog)]
    conversation += [{"role": m["role"], "content": m["content"]} for m in messages]

    for _attempt in range(MAX_REPAIRS + 1):
        reply = llm.complete(conversation, tools())
        if not reply.tool_calls:
            text = clean_text(reply.content, MAX_QUESTION_CHARS)
            if text:
                return {"reply": text, "proposal": None}
            raise LlmError("no tool call and no text")
        call = reply.tool_calls[0]
        try:
            return _handle_call(call.name, call.arguments, design, revision, catalog, signing_key)
        except _Rejected as rejection:
            conversation.append(reply.as_message())
            # Every tool call in the assistant message needs a matching tool result.
            for other in reply.tool_calls:
                result = str(rejection) if other.id == call.id else "Ignored: call one tool at a time."
                conversation.append({"role": "tool", "tool_call_id": other.id, "content": result})
    return {"reply": FALLBACK_REPLY, "proposal": None}


def _handle_call(name: str, arguments: str, design: dict, revision: int, catalog: dict, signing_key: str) -> dict:
    try:
        args = json.loads(arguments) if arguments else {}
    except ValueError:
        raise _Rejected("The arguments were not valid JSON. Call the tool again with valid JSON.") from None
    if not isinstance(args, dict):
        raise _Rejected("The arguments must be a JSON object.")

    if name == CLARIFY:
        question = clean_text(args.get("question"), MAX_QUESTION_CHARS)
        if not question:
            raise _Rejected("`question` must be a non-empty string.")
        return {"reply": question, "proposal": None}
    if name != PROPOSE:
        raise _Rejected(f"Unknown tool. Use `{PROPOSE}` or `{CLARIFY}`.")

    raw_ops = args.get("ops")
    try:
        parsed = parse_ops(raw_ops)
        if not parsed:
            raise _Rejected("`ops` must contain at least one op.")
        # Canonical form: what is signed is exactly what the engine parsed.
        ops = [op.model_dump(by_alias=True, exclude_none=True, mode="json") for op in parsed]
        apply_ops(design, ops, catalog)  # dry run; the result is discarded
    except DomainError as error:
        raise _Rejected(
            f"That proposal is invalid: {error.code} at {error.path}: {error.message}. Fix it and call the tool again."
        ) from None

    summary = clean_text(args.get("summary"), MAX_SUMMARY_CHARS) or DEFAULT_SUMMARY
    proposal_id = f"prop_{uuid.uuid4().hex}"
    base_hash = signing.design_hash(design)
    proposal = {
        "proposalId": proposal_id,
        "baseRevision": revision,
        "baseHash": base_hash,
        "ops": ops,
        "summary": summary,
        "changes": describe_ops(parsed, design, catalog),
        "signature": signing.sign(signing_key, proposal_id, ops, revision, base_hash),
    }
    return {"reply": summary, "proposal": proposal}
