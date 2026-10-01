"""Application settings, read from environment variables (or a .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

try:  # optional: load a local .env during development
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # "azure" | "openai" | "mock" | "auto" (auto picks azure, then openai, then mock)
    llm_provider: str = "auto"

    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4"
    azure_openai_api_version: str = "2024-06-01"

    openai_api_key: str = ""
    openai_model: str = "gpt-4"

    temperature: float = 0.3
    max_tokens: int = 600
    request_timeout: float = 30.0

    max_message_chars: int = 2000
    max_history_turns: int = 6
    redact_pii: bool = True
    allowed_origins: tuple[str, ...] = ("*",)

    @classmethod
    def from_env(cls) -> "Settings":
        origins = os.getenv("ALLOWED_ORIGINS", "*")
        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "auto").strip().lower(),
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4"),
            azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "600")),
            request_timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
            max_message_chars=int(os.getenv("MAX_MESSAGE_CHARS", "2000")),
            max_history_turns=int(os.getenv("MAX_HISTORY_TURNS", "6")),
            redact_pii=_bool("REDACT_PII", True),
            allowed_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
