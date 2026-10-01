"""Language-model providers.

``AzureOpenAIProvider`` calls a GPT-4 deployment on Azure OpenAI Service,
``OpenAIProvider`` calls the OpenAI API directly, and ``MockProvider`` returns a
deterministic, lexicon-grounded answer so the whole app (UI, API, tests,
evaluation) runs without credentials.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Protocol

from .config import Settings

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when the upstream model call fails."""


@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str
    latency_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class LLMProvider(Protocol):
    name: str
    model: str

    def complete(self, messages: list[dict], *, temperature: float | None = None,
                 max_tokens: int | None = None, json_mode: bool = False) -> LLMResponse: ...


class _OpenAICompatibleProvider:
    """Shared implementation for the OpenAI and Azure OpenAI chat completion APIs."""

    name = "openai"

    def __init__(self, client, model: str, settings: Settings):
        self._client = client
        self.model = model
        self._settings = settings

    def complete(self, messages, *, temperature=None, max_tokens=None, json_mode=False) -> LLMResponse:
        kwargs = dict(
            model=self.model,
            messages=messages,
            temperature=self._settings.temperature if temperature is None else temperature,
            max_tokens=max_tokens or self._settings.max_tokens,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        start = time.perf_counter()
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except Exception as exc:  # network, auth, rate limit, content filter...
            log.warning("LLM call failed: %s", exc)
            raise LLMError(f"{self.name} request failed: {type(exc).__name__}") from exc
        latency = int((time.perf_counter() - start) * 1000)
        choice = resp.choices[0]
        usage = getattr(resp, "usage", None)
        return LLMResponse(
            text=(choice.message.content or "").strip(),
            model=getattr(resp, "model", self.model) or self.model,
            provider=self.name,
            latency_ms=latency,
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
        )


class OpenAIProvider(_OpenAICompatibleProvider):
    name = "openai"

    def __init__(self, settings: Settings):
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key, timeout=settings.request_timeout, max_retries=2)
        super().__init__(client, settings.openai_model, settings)


class AzureOpenAIProvider(_OpenAICompatibleProvider):
    name = "azure"

    def __init__(self, settings: Settings):
        from openai import AzureOpenAI

        client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            timeout=settings.request_timeout,
            max_retries=2,
        )
        # On Azure, "model" is the *deployment name* you created in the portal.
        super().__init__(client, settings.azure_openai_deployment, settings)


class MockProvider:
    """Offline stand-in for GPT-4.

    Builds an answer from the recognized-terms context that the chat service
    puts in the system prompt. It is clearly labelled as demo mode in the UI.
    """

    name = "mock"
    model = "mock-gpt-4"

    def complete(self, messages, *, temperature=None, max_tokens=None, json_mode=False) -> LLMResponse:
        start = time.perf_counter()
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        question = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

        if json_mode:
            text = json.dumps({"terms": []})
        else:
            text = self._compose(system, question)
        return LLMResponse(text=text, model=self.model, provider=self.name,
                           latency_ms=int((time.perf_counter() - start) * 1000))

    @staticmethod
    def _compose(system: str, question: str) -> str:
        terms = re.findall(r"^- (.+?) \[(\w+)\](?: \(NEGATED\))?: (.+)$", system, flags=re.MULTILINE)
        negated = set(re.findall(r"^- (.+?) \[\w+\] \(NEGATED\)", system, flags=re.MULTILINE))
        lines = ["**Demo mode** (no GPT-4 connection is configured, so this answer is assembled from MedChat's built-in glossary)."]
        present = [(t, c, d) for t, c, d in terms if t not in negated]
        if present:
            lines.append("")
            lines.append("Here's some general background on the terms in your question:")
            for term, category, definition in present[:6]:
                lines.append(f"- **{term}** ({category}): {definition}")
        if negated:
            lines.append("")
            lines.append("You mentioned you do *not* have: " + ", ".join(sorted(negated)) + ".")
        if not terms:
            lines.append("")
            lines.append("I didn't recognize specific medical terms in your question. Could you describe the symptom, condition, or medication you're asking about?")
        lines.append("")
        lines.append("For advice about your own situation, please talk with a doctor, nurse, or pharmacist.")
        return "\n".join(lines)


def build_provider(settings: Settings) -> LLMProvider:
    choice = settings.llm_provider
    if choice == "auto":
        if settings.azure_openai_endpoint and settings.azure_openai_api_key:
            choice = "azure"
        elif settings.openai_api_key:
            choice = "openai"
        else:
            choice = "mock"

    if choice == "azure":
        if not (settings.azure_openai_endpoint and settings.azure_openai_api_key):
            raise ValueError("LLM_PROVIDER=azure requires AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY")
        return AzureOpenAIProvider(settings)
    if choice == "openai":
        if not settings.openai_api_key:
            raise ValueError("LLM_PROVIDER=openai requires OPENAI_API_KEY")
        return OpenAIProvider(settings)
    if choice == "mock":
        return MockProvider()
    raise ValueError(f"Unknown LLM_PROVIDER '{settings.llm_provider}' (use azure, openai, mock or auto)")
