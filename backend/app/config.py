"""Application settings loaded from environment variables."""

import logging
import secrets
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Environments where the scripted fake agent may run (tests and Playwright only).
FAKE_AGENT_ENVS = frozenset({"test", "e2e"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    cors_origins: str = "http://localhost:5173"

    # ASSUMPTION: the model name is a configurable default, not a fixed choice.
    openai_api_key: SecretStr | None = None
    openai_chat_model: str = "gpt-5.4-mini-2026-03-17"
    openai_timeout_seconds: float = 30.0
    agent_mode: Literal["openai", "fake"] = "openai"

    proposal_signing_key: SecretStr | None = None

    # Per-client limit on /api/chat (each turn may call the LLM up to 3 times).
    chat_rate_limit_per_minute: int = 20

    @field_validator("openai_chat_model", mode="before")
    @classmethod
    def _default_model_when_blank(cls, value: object) -> object:
        # `.env.example` ships `OPENAI_CHAT_MODEL=` empty: treat that as "use the default".
        if isinstance(value, str) and not value.strip():
            return cls.model_fields["openai_chat_model"].default
        return value

    @model_validator(mode="after")
    def _check_environment(self) -> "Settings":
        if self.agent_mode == "fake" and self.app_env not in FAKE_AGENT_ENVS:
            raise ValueError("AGENT_MODE=fake is only allowed when APP_ENV is test or e2e")
        if not (self.openai_api_key and self.openai_api_key.get_secret_value().strip()):
            self.openai_api_key = None
        if not (self.proposal_signing_key and self.proposal_signing_key.get_secret_value().strip()):
            if self.app_env == "production":
                raise ValueError("PROPOSAL_SIGNING_KEY must be set in production")
            # Proposals are only valid for this process; fine for local development.
            logger.warning("PROPOSAL_SIGNING_KEY is not set: using a random per-process key")
            self.proposal_signing_key = SecretStr(secrets.token_urlsafe(32))
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def agent_available(self) -> bool:
        return self.agent_mode == "fake" or self.openai_api_key is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
