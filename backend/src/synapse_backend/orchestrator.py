"""Shared orchestrator construction — importable by app.py and api.py."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from synapse_ai.agent.orchestrator import AnswerResult, Orchestrator
from synapse_ai.clients.openai_client import OpenAIClient
from synapse_ai.vectorstore.store import Document, VectorStore

from synapse_backend.config import settings
from synapse_backend.services.github_mcp_client import GitHubMCPClient
from synapse_backend.services.rts_client import RTSClient

logger = logging.getLogger(__name__)

_orchestrator: Orchestrator | None = None

# Path to sample fixtures relative to repo root (ai-ml/tests/fixtures/sample_docs.json)
_SAMPLE_DOCS_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "ai-ml" / "tests" / "fixtures" / "sample_docs.json"
)


def ensure_vector_store_seeded() -> None:
    """If the vector store is empty, seed it from the test fixtures.

    Called once at startup by both app.py and api.py so a fresh Render
    deploy gets a populated vector store without committing binary data.
    """
    if not _SAMPLE_DOCS_PATH.exists():
        logger.info("Sample docs fixture not found at %s — skipping auto-seed", _SAMPLE_DOCS_PATH)
        return

    client = OpenAIClient()
    store = VectorStore(embed_fn=client.embed)
    if store.count() > 0:
        logger.info("Vector store already has %d documents — no seeding needed", store.count())
        return

    logger.info("Vector store is empty — seeding from %s", _SAMPLE_DOCS_PATH)
    with _SAMPLE_DOCS_PATH.open("r", encoding="utf-8") as f:
        records = json.load(f)
    docs = [Document(r["text"], r.get("metadata", {})) for r in records]
    store.add(docs)
    store.persist()
    logger.info("Seeded %d documents into vector store", len(docs))


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator(
            github_client=GitHubMCPClient() if settings.github_token else None,
            rts_client=RTSClient() if settings.slack_user_token else None,
        )
    return _orchestrator
