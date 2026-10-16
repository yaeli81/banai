"""POST /api/chat: one agent turn. Stateless; never changes or stores the design."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from app.agent.llm import FakeLlm, LlmClient, LlmError, OpenAiLlm
from app.agent.orchestrator import run_turn
from app.api.errors import domain_error_response, error_response
from app.api.rate_limit import RateLimiter
from app.config import Settings, get_settings
from app.domain.apply import apply_ops
from app.domain.catalog import load_catalog
from app.domain.errors import DomainError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

MAX_MESSAGES = 20
MAX_MESSAGE_CHARS = 2000


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: Annotated[str, Field(min_length=1, max_length=MAX_MESSAGE_CHARS)]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: Annotated[list[ChatMessage], Field(min_length=1, max_length=MAX_MESSAGES)]
    design: dict
    revision: Annotated[int, Field(ge=1, le=1_000_000_000)]


@lru_cache
def _limiter(limit: int) -> RateLimiter:
    return RateLimiter(limit)


def get_llm(settings: Annotated[Settings, Depends(get_settings)]) -> LlmClient | None:
    if settings.agent_mode == "fake":
        return FakeLlm()
    if settings.openai_api_key is None:
        return None
    return OpenAiLlm(settings.openai_api_key.get_secret_value(), settings.openai_chat_model,
                     settings.openai_timeout_seconds)


@router.post("/chat")
def chat(
    body: ChatRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    llm: Annotated[LlmClient | None, Depends(get_llm)],
):
    client = request.client.host if request.client else "unknown"
    if not _limiter(settings.chat_rate_limit_per_minute).allow(client):
        return error_response(429, "RATE_LIMITED", "Too many messages. Please wait a minute and try again.")
    if body.messages[-1].role != "user":
        return error_response(422, "INVALID_REQUEST", "The last message must come from the customer.")
    if llm is None:
        return error_response(503, "AGENT_UNAVAILABLE", "The AI designer is not configured on this server.")

    catalog = load_catalog()
    try:
        design = apply_ops(body.design, [], catalog)  # parse + full validation, canonical copy
    except DomainError as error:
        return domain_error_response(error)

    try:
        result = run_turn(
            messages=[m.model_dump() for m in body.messages], design=design, revision=body.revision,
            catalog=catalog, llm=llm, signing_key=settings.proposal_signing_key.get_secret_value(),
        )
    except LlmError as error:
        logger.warning("agent turn failed: %s", error)
        return error_response(502, "AGENT_ERROR", "The AI designer is unavailable right now. Please try again.")
    return {"success": True, "data": result, "error": None}
