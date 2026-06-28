"""FastAPI application exposing /internal/answer for the companion web frontend.

Run as a separate process::

    python -m synapse_backend.api

Or::

    uvicorn synapse_backend.api:app --port 8000
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load backend/.env into os.environ BEFORE any Settings class is imported
_BACKEND_ENV = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_BACKEND_ENV)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from uvicorn import run

from synapse_backend.config import settings
from synapse_backend.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)

app = FastAPI(title="Synapse Internal API")

# ── CORS ──────────────────────────────────────────────────────────────────
# Allow all origins for local development.  Restrict this before any real
# public deployment (e.g. set allow_origins to the frontend's origin).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request / response models ─────────────────────────────────────────────


class AnswerRequest(BaseModel):
    question: str


class SourceItem(BaseModel):
    type: str = "web"
    title: str
    url: str = ""
    snippet: str = ""
    timestamp: str = ""


class AnswerResponse(BaseModel):
    answer_markdown: str
    confidence: str
    sources: list[SourceItem]
    decision_detected: bool


# ── Routes ────────────────────────────────────────────────────────────────


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/answer", response_model=AnswerResponse)
def answer(request: AnswerRequest) -> Any:
    try:
        result = get_orchestrator().answer(
            request.question, conversation_transcript=request.question
        )
    except Exception as exc:
        logger.exception("Orchestrator failed")
        raise HTTPException(status_code=500, detail=str(exc))

    sources = [
        SourceItem(
            type=s.type,
            title=s.title,
            url=s.url,
            snippet=s.snippet,
            timestamp="",
        )
        for s in result.sources
    ]

    return AnswerResponse(
        answer_markdown=result.answer_markdown,
        confidence=result.confidence,
        sources=sources,
        decision_detected=result.decision_detected,
    )


# ── CLI entry point ───────────────────────────────────────────────────────


def start() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting Synapse API server on port %s ...", settings.api_port)
    run("synapse_backend.api:app", host="0.0.0.0", port=settings.api_port, reload=False)


if __name__ == "__main__":
    start()
