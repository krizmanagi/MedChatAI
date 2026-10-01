"""FastAPI application: JSON API + static chat frontend."""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import __version__
from .chat import ChatService, ChatTurn
from .config import Settings, get_settings
from .llm import build_provider
from .terminology import get_recognizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("medchat")

STATIC_DIR = Path(__file__).resolve().parent.parent / "frontend"


# ------------------------------------------------------------------ schemas

class HistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[HistoryTurn] = Field(default_factory=list, max_length=40)

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be blank")
        return v.strip()


class TermsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class TermOut(BaseModel):
    concept_id: str | None
    term: str
    category: str
    text: str
    start: int
    end: int
    match_type: str
    confidence: float
    negated: bool
    definition: str


class SafetyOut(BaseModel):
    emergency: bool
    emergency_reasons: list[str]
    crisis: bool
    redactions: list[str]


class ChatResponse(BaseModel):
    request_id: str
    reply: str
    terms: list[TermOut]
    safety: SafetyOut
    provider: str
    model: str
    latency_ms: int
    degraded: bool
    notices: list[str]


# ------------------------------------------------------------- rate limiting

class RateLimiter:
    """Simple in-memory sliding-window limiter (per client IP)."""

    def __init__(self, limit: int = 20, window_seconds: int = 60):
        self.limit, self.window = limit, window_seconds
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> bool:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


# --------------------------------------------------------------------- app

def create_app(settings: Settings | None = None, service: ChatService | None = None) -> FastAPI:
    settings = settings or get_settings()
    recognizer = get_recognizer()
    if service is None:
        service = ChatService(settings, build_provider(settings), recognizer)
    limiter = RateLimiter()

    app = FastAPI(
        title="MedChat AI",
        version=__version__,
        description="Healthcare-focused chatbot with medical terminology recognition (Python, Azure OpenAI GPT-4).",
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=list(settings.allowed_origins),
        allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
    )
    app.state.service = service

    def rate_limited(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        if not limiter.check(client):
            raise HTTPException(status_code=429, detail="Too many requests. Please wait a minute and try again.")

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "version": __version__,
            "provider": service.provider.name,
            "model": service.provider.model,
            "lexicon_version": recognizer.version,
            "concepts": len(recognizer.concepts),
        }

    @app.post("/api/chat", response_model=ChatResponse, dependencies=[Depends(rate_limited)])
    def chat(req: ChatRequest):
        if len(req.message) > settings.max_message_chars:
            raise HTTPException(status_code=422,
                                detail=f"Message is too long (max {settings.max_message_chars} characters).")
        history = [ChatTurn(t.role, t.content) for t in req.history]
        result = service.answer(req.message, history)
        log.info("chat request=%s provider=%s terms=%d emergency=%s latency_ms=%d",
                 result.request_id, result.provider, len(result.terms),
                 result.safety["emergency"], result.latency_ms)
        return result.to_dict()

    @app.post("/api/terms")
    def terms(req: TermsRequest):
        return recognizer.recognize(req.text).to_dict()

    @app.get("/api/concepts/{concept_id}")
    def concept(concept_id: str):
        c = recognizer.get(concept_id)
        if c is None:
            raise HTTPException(status_code=404, detail="Unknown concept")
        return {"id": c.id, "term": c.term, "category": c.category, "definition": c.definition,
                "synonyms": list(c.synonyms), "abbreviations": list(c.abbreviations)}

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):  # pragma: no cover - safety net
        log.exception("unhandled error: %s", exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
