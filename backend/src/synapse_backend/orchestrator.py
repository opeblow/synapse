"""Shared orchestrator construction — importable by app.py and api.py."""

from __future__ import annotations

from synapse_ai.agent.orchestrator import AnswerResult, Orchestrator

from synapse_backend.config import settings
from synapse_backend.services.github_mcp_client import GitHubMCPClient
from synapse_backend.services.rts_client import RTSClient

_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator(
            github_client=GitHubMCPClient() if settings.github_token else None,
            rts_client=RTSClient() if settings.slack_user_token else None,
        )
    return _orchestrator
