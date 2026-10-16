"""Speech clients for the chained voice pipeline: audio -> text (then the normal chat agent) -> audio.

Voice never talks to the agent itself: the transcript is sent to /api/chat like a typed message,
and only the agent's already guard-railed reply is spoken. `FakeVoice` is the network-free
stand-in for tests and Playwright (AGENT_MODE=fake, test/e2e only).
"""

from __future__ import annotations

import io
import struct
from typing import Protocol

from app.agent.llm import LlmError

def _silent_wav(seconds: float = 0.05, rate: int = 16_000) -> bytes:
    """A valid, silent 16-bit mono WAV so the browser can "play" the fake reply."""
    data = bytes(2 * int(seconds * rate))  # 16-bit zero samples
    header = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
    return header + b"data" + struct.pack("<I", len(data)) + data


# Domain vocabulary that biases transcription (it does not force a language).
TRANSCRIBE_PROMPT = (
    "Wardrobe design. wardrobe, compartment, shelf, drawer, hanging rail, hinged doors, sliding doors, "
    "width, height, depth, cm. ארון, תא, מדף, מגירה, מוט תלייה, דלתות ציר, דלתות הזזה, רוחב, גובה, עומק, ס״מ."
)

# File-name extension per accepted content type (the SDK infers the format from the name).
EXTENSIONS = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "mp4", "audio/mpeg": "mp3", "audio/wav": "wav"}


class VoiceClient(Protocol):
    def transcribe(self, audio: bytes, content_type: str) -> str: ...

    def speak(self, text: str) -> tuple[bytes, str]:
        """Returns (audio, media type)."""
        ...


class OpenAiVoice:
    def __init__(self, api_key: str, transcribe_model: str, tts_model: str, voice: str, timeout_seconds: float) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=1)
        self._transcribe_model = transcribe_model
        self._tts_model = tts_model
        self._voice = voice

    def transcribe(self, audio: bytes, content_type: str) -> str:
        import openai

        upload = io.BytesIO(audio)
        upload.name = f"speech.{EXTENSIONS[content_type]}"
        try:
            result = self._client.audio.transcriptions.create(
                model=self._transcribe_model, file=upload, prompt=TRANSCRIBE_PROMPT)
        except openai.OpenAIError as error:
            raise LlmError(type(error).__name__) from error
        return result.text or ""

    def speak(self, text: str) -> tuple[bytes, str]:
        import openai

        try:
            response = self._client.audio.speech.create(
                model=self._tts_model, voice=self._voice, input=text, response_format="mp3",
                instructions="Speak warmly and clearly, at a calm pace, in the language of the text.",
            )
            return response.read(), "audio/mpeg"
        except openai.OpenAIError as error:
            raise LlmError(type(error).__name__) from error


class FakeVoice:
    TRANSCRIPT = "Make it 240 cm wide"

    def transcribe(self, audio: bytes, content_type: str) -> str:
        return self.TRANSCRIPT

    def speak(self, text: str) -> tuple[bytes, str]:
        return _silent_wav(), "audio/wav"
