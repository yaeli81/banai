"""/api/voice/* with fake or scripted speech clients (no network)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.agent.llm import LlmError
from app.agent.voice import FakeVoice
from app.api.voice import MAX_AUDIO_BYTES, get_voice
from app.config import Settings, get_settings
from app.main import app

AUDIO = b"\x1aE\xdf\xa3" + b"\x00" * 2048  # looks like a small webm


def settings(**overrides) -> Settings:
    values = {"app_env": "test", "proposal_signing_key": SecretStr("k"), "openai_api_key": SecretStr("sk-test"),
              "chat_rate_limit_per_minute": 1000, **overrides}
    return Settings(_env_file=None, **values)


class Recording:
    def __init__(self, transcript="Make it 240 cm wide", fail=False):
        self.transcript, self.fail = transcript, fail
        self.received: list[tuple[int, str]] = []
        self.spoken: list[str] = []

    def transcribe(self, audio, content_type):
        if self.fail:
            raise LlmError("RateLimitError: account details")
        self.received.append((len(audio), content_type))
        return self.transcript

    def speak(self, text):
        if self.fail:
            raise LlmError("APIConnectionError")
        self.spoken.append(text)
        return b"ID3fake", "audio/mpeg"


@pytest.fixture
def voice():
    fake = Recording()
    app.dependency_overrides[get_settings] = lambda: settings()
    app.dependency_overrides[get_voice] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


client = TestClient(app)


def post_audio(body=AUDIO, content_type="audio/webm;codecs=opus"):
    return client.post("/api/voice/transcribe", content=body, headers={"content-type": content_type})


def test_transcribe_returns_text_only(voice):
    response = post_audio()
    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"text": "Make it 240 cm wide"}, "error": None}
    assert voice.received == [(len(AUDIO), "audio/webm")]


@pytest.mark.parametrize("content_type", ["audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav"])
def test_supported_recording_formats(voice, content_type):
    assert post_audio(content_type=content_type).status_code == 200


@pytest.mark.parametrize("content_type", ["application/json", "text/plain", "video/mp4", ""])
def test_other_formats_are_415(voice, content_type):
    response = post_audio(content_type=content_type)
    assert response.status_code == 415 and voice.received == []


def test_empty_recording_is_422(voice):
    assert post_audio(body=b"").status_code == 422


def test_too_long_recording_is_413(voice):
    assert post_audio(body=b"\x00" * (MAX_AUDIO_BYTES + 1)).status_code == 413
    assert voice.received == []


def test_transcript_is_cleaned(voice):
    voice.transcript = "make it‮ wider\n\n\nplease\x07"
    assert post_audio().json()["data"]["text"] == "make it wider please"


def test_speech_returns_audio(voice):
    response = client.post("/api/voice/speech", json={"text": "I suggest widening it to 240 cm."})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.headers["cache-control"] == "no-store"
    assert response.content == b"ID3fake"
    assert voice.spoken == ["I suggest widening it to 240 cm."]


@pytest.mark.parametrize("body", [{"text": ""}, {"text": "x" * 201}, {"text": "hi", "voice": "evil"}, {}])
def test_speech_input_limits(voice, body):
    assert client.post("/api/voice/speech", json=body).status_code == 422
    assert voice.spoken == []


def test_speech_of_only_invisible_characters_is_422(voice):
    assert client.post("/api/voice/speech", json={"text": "​‮"}).status_code == 422


def test_failures_are_a_generic_502(voice):
    voice.fail = True
    response = post_audio()
    assert response.status_code == 502 and "account" not in response.text
    assert client.post("/api/voice/speech", json={"text": "hi"}).status_code == 502


def test_unavailable_without_a_key():
    app.dependency_overrides[get_settings] = lambda: settings(openai_api_key=None)
    try:
        assert post_audio().status_code == 503
        assert client.post("/api/voice/speech", json={"text": "hi"}).json()["error"]["code"] == "AGENT_UNAVAILABLE"
    finally:
        app.dependency_overrides.clear()


def test_voice_shares_the_chat_rate_limit(voice):
    app.dependency_overrides[get_settings] = lambda: settings(chat_rate_limit_per_minute=3)
    codes = [post_audio().status_code, client.post("/api/voice/speech", json={"text": "hi"}).status_code,
             post_audio().status_code, post_audio().status_code]
    assert codes == [200, 200, 200, 429]


def test_fake_voice_is_used_in_fake_mode():
    from app.api.voice import get_voice as real_get_voice

    assert isinstance(real_get_voice(settings(agent_mode="fake")), FakeVoice)
    assert real_get_voice(settings(openai_api_key=None)) is None


def test_voice_model_defaults_apply_when_blank():
    configured = Settings(_env_file=None, openai_transcribe_model="", openai_tts_model=" ", openai_tts_voice="")
    assert configured.openai_transcribe_model.startswith("gpt-4o-mini-transcribe")
    assert configured.openai_tts_model.startswith("gpt-4o-mini-tts") and configured.openai_tts_voice == "alloy"
