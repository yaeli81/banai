"""Voice endpoints for the chained pipeline. Stateless; audio is never stored or logged.

/transcribe turns recorded audio into text only. The client then sends that text to /api/chat
like a typed message, so the agent, its validation and its guardrails are exactly the same.
/speech reads a short reply aloud.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.agent.llm import LlmError
from app.agent.orchestrator import clean_text
from app.agent.voice import EXTENSIONS, FakeVoice, OpenAiVoice, VoiceClient
from app.api.chat import MAX_MESSAGE_CHARS, _limiter
from app.api.errors import error_response
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/voice")

MAX_AUDIO_BYTES = 1024 * 1024  # ~60 s of opus speech; the recorder stops itself after 30 s
MAX_SPEECH_CHARS = 200  # replies are <= 105 characters; headroom for short system notes


class SpeechRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: Annotated[str, Field(min_length=1, max_length=MAX_SPEECH_CHARS)]


def get_voice(settings: Annotated[Settings, Depends(get_settings)]) -> VoiceClient | None:
    if settings.agent_mode == "fake":
        return FakeVoice()
    if settings.openai_api_key is None:
        return None
    return OpenAiVoice(settings.openai_api_key.get_secret_value(), settings.openai_transcribe_model,
                       settings.openai_tts_model, settings.openai_tts_voice, settings.openai_timeout_seconds)


def _guard(request: Request, settings: Settings, voice: VoiceClient | None):
    client = request.client.host if request.client else "unknown"
    if not _limiter(settings.chat_rate_limit_per_minute).allow(client):
        return error_response(429, "RATE_LIMITED", "Too many requests. Please wait a minute and try again.")
    if voice is None:
        return error_response(503, "AGENT_UNAVAILABLE", "The AI designer is not configured on this server.")
    return None


def _media_type(request: Request) -> str:
    # "audio/webm;codecs=opus" -> "audio/webm"
    return request.headers.get("content-type", "").split(";", 1)[0].strip().lower()


@router.post("/transcribe")
async def transcribe(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    voice: Annotated[VoiceClient | None, Depends(get_voice)],
):
    media_type = _media_type(request)
    if media_type not in EXTENSIONS:
        return error_response(415, "UNSUPPORTED_AUDIO", "This audio format is not supported.")
    audio = bytearray()
    async for chunk in request.stream():  # bounded read: never buffer more than the cap
        audio += chunk
        if len(audio) > MAX_AUDIO_BYTES:
            return error_response(413, "TOO_LARGE", "The recording is too long.")
    if not audio:
        return error_response(422, "INVALID_REQUEST", "The recording is empty.")
    blocked = _guard(request, settings, voice)
    if blocked:
        return blocked
    try:
        text = voice.transcribe(bytes(audio), media_type)
    except LlmError as error:
        logger.warning("transcription failed: %s", error)
        return error_response(502, "AGENT_ERROR", "Speech could not be processed right now. Please try again.")
    return {"success": True, "data": {"text": clean_text(text, MAX_MESSAGE_CHARS)}, "error": None}


@router.post("/speech")
def speech(
    body: SpeechRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    voice: Annotated[VoiceClient | None, Depends(get_voice)],
):
    blocked = _guard(request, settings, voice)
    if blocked:
        return blocked
    text = clean_text(body.text, MAX_SPEECH_CHARS)
    if not text:
        return error_response(422, "INVALID_REQUEST", "There is nothing to read aloud.")
    try:
        audio, media_type = voice.speak(text)
    except LlmError as error:
        logger.warning("speech failed: %s", error)
        return error_response(502, "AGENT_ERROR", "Speech could not be generated right now.")
    return Response(content=audio, media_type=media_type, headers={"Cache-Control": "no-store"})
