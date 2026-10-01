"""Chat orchestration: safety checks -> term recognition -> GPT-4 -> structured reply."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field

from .config import Settings
from .llm import LLMError, LLMProvider
from .prompts import EXTRACTION_PROMPT, SYSTEM_PROMPT, format_term_context
from .safety import CRISIS_MESSAGE, EMERGENCY_MESSAGE, assess
from .terminology import TermMatch, TerminologyRecognizer

log = logging.getLogger(__name__)

FALLBACK_REPLY = (
    "Sorry, I couldn't reach the language model just now. Please try again in a moment. "
    "The medical terms I recognized in your question are listed alongside this message."
)


@dataclass
class ChatTurn:
    role: str      # "user" | "assistant"
    content: str


@dataclass
class ChatResult:
    request_id: str
    reply: str
    terms: list[dict]
    safety: dict
    provider: str
    model: str
    latency_ms: int
    degraded: bool = False
    notices: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class ChatService:
    def __init__(self, settings: Settings, provider: LLMProvider, recognizer: TerminologyRecognizer):
        self.settings = settings
        self.provider = provider
        self.recognizer = recognizer

    def answer(self, message: str, history: list[ChatTurn] | None = None) -> ChatResult:
        started = time.perf_counter()
        request_id = uuid.uuid4().hex[:12]

        safety = assess(message, redact=self.settings.redact_pii)
        recognition = self.recognizer.recognize(message)
        terms = [m.to_dict() for m in recognition.matches]
        notices: list[str] = []
        if safety.redactions:
            notices.append("Personal details (" + ", ".join(safety.redactions).lower().replace("_", " ")
                           + ") were removed before your question was sent to the AI model.")

        # Self-harm language: respond with crisis resources immediately; do not call the model.
        if safety.crisis:
            return ChatResult(request_id, CRISIS_MESSAGE, terms, safety.to_dict(), "safety", "rule-based",
                              int((time.perf_counter() - started) * 1000), notices=notices)

        messages = self._build_messages(safety.sanitized_text, terms, history or [])
        degraded = False
        try:
            resp = self.provider.complete(messages)
            reply, provider, model = resp.text, resp.provider, resp.model
        except LLMError as exc:
            log.error("request %s: %s", request_id, exc)
            reply, provider, model, degraded = FALLBACK_REPLY, self.provider.name, self.provider.model, True

        if safety.emergency:
            reply = f"**{EMERGENCY_MESSAGE}**\n\n{reply}"

        return ChatResult(
            request_id=request_id, reply=reply, terms=terms, safety=safety.to_dict(),
            provider=provider, model=model, latency_ms=int((time.perf_counter() - started) * 1000),
            degraded=degraded, notices=notices,
        )

    def _build_messages(self, sanitized: str, terms: list[dict], history: list[ChatTurn]) -> list[dict]:
        system = SYSTEM_PROMPT + "\n" + format_term_context(terms)
        messages = [{"role": "system", "content": system}]
        max_msgs = self.settings.max_history_turns * 2
        for turn in history[-max_msgs:]:
            if turn.role in {"user", "assistant"} and turn.content.strip():
                content = turn.content[: self.settings.max_message_chars * 2]
                if turn.role == "user" and self.settings.redact_pii:
                    content = assess(content).sanitized_text
                messages.append({"role": turn.role, "content": content})
        messages.append({"role": "user", "content": sanitized})
        return messages


class LLMTermExtractor:
    """Uses GPT-4 to extract medical terms, then normalizes them against the lexicon.

    Used by the evaluation harness to compare lexicon-only, LLM-only and hybrid
    recognition. Terms the lexicon cannot normalize are reported with
    ``concept_id = None``.
    """

    def __init__(self, provider: LLMProvider, recognizer: TerminologyRecognizer):
        self.provider = provider
        self.recognizer = recognizer

    def extract(self, text: str) -> list[TermMatch]:
        resp = self.provider.complete(
            [{"role": "system", "content": EXTRACTION_PROMPT}, {"role": "user", "content": text}],
            temperature=0, max_tokens=400, json_mode=True,
        )
        try:
            payload = json.loads(resp.text)
            items = payload.get("terms", []) if isinstance(payload, dict) else []
        except json.JSONDecodeError:
            log.warning("extractor returned non-JSON output")
            items = []

        results: list[TermMatch] = []
        for item in items:
            surface = str(item.get("text", "")).strip()
            if not surface:
                continue
            normalized = self.recognizer.recognize(surface).matches
            start = text.lower().find(surface.lower())
            if normalized:
                best = max(normalized, key=lambda m: m.end - m.start)
                concept = self.recognizer.get(best.concept_id)
                results.append(TermMatch(
                    concept_id=best.concept_id, term=concept.term, category=concept.category,
                    text=surface, start=max(start, 0), end=max(start, 0) + len(surface),
                    match_type="llm", confidence=0.9, negated=bool(item.get("negated")),
                    definition=concept.definition,
                ))
            else:
                results.append(TermMatch(
                    concept_id=None, term=surface, category=str(item.get("category", "unknown")),
                    text=surface, start=max(start, 0), end=max(start, 0) + len(surface),
                    match_type="llm-unmapped", confidence=0.6, negated=bool(item.get("negated")),
                ))
        return results


def parse_history(raw: list[dict] | None) -> list[ChatTurn]:
    turns = []
    for item in raw or []:
        role, content = item.get("role"), item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            turns.append(ChatTurn(role, re.sub(r"\s+\n", "\n", content)))
    return turns
