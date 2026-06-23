"""Bolt application entry point for Synapse Slack bot."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env into os.environ BEFORE any Settings class is imported,
# so both synapse_backend.config.settings and synapse_ai.config.settings
# read the same values regardless of process CWD.
_BACKEND_ENV = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_BACKEND_ENV)

import logging

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from synapse_ai.agent.orchestrator import AnswerResult, Orchestrator

from synapse_backend.config import settings
from synapse_backend.services.github_mcp_client import GitHubMCPClient
from synapse_backend.views import answer_message_view, decision_card_view

logger = logging.getLogger(__name__)

app = App(token=settings.slack_bot_token, signing_secret=settings.slack_signing_secret)

# Lazy: resolved inside start() so tests can import the module without a live Slack API call
_bot_user_id_resolved = False

# Lazy orchestrator so tests / env lacking AI keys don't fail on import
_orchestrator: Orchestrator | None = None


def _get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator(
            github_client=GitHubMCPClient() if settings.github_token else None,
        )
    return _orchestrator


def _post_decision_card_if_needed(result: AnswerResult, question: str) -> None:
    """Post a Decision Card to the decisions channel if a decision was detected."""
    signal = result.decision_signal
    if not signal or not signal.is_decision:
        return
    channel = settings.slack_decisions_channel_id
    if not channel:
        logger.warning("slack_decisions_channel_id not set — skipping Decision Card")
        return
    try:
        fallback = signal.summary or "Decision detected"
        app.client.chat_postMessage(
            channel=channel,
            blocks=decision_card_view(signal, question),
            text=fallback,
        )
    except Exception:
        logger.exception("Failed to post Decision Card")


@app.event("message")
def handle_message(event: dict, say) -> None:
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return
    if event.get("channel_type") != "im":
        return

    text = event.get("text", "")
    logger.info("Received DM: %s", text)

    try:
        result = _get_orchestrator().answer(text, conversation_transcript=text)
        say(blocks=answer_message_view(result), text=result.answer_markdown)
        _post_decision_card_if_needed(result, text)
    except Exception:
        logger.exception("Failed to answer question")
        say("Sorry, I encountered an error while processing your question.")


@app.event("app_mention")
def handle_mention(event: dict, say) -> None:
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return

    text = event.get("text", "")
    logger.info("Received mention: %s", text)

    try:
        result = _get_orchestrator().answer(text, conversation_transcript=text)
        say(blocks=answer_message_view(result), text=result.answer_markdown)
        _post_decision_card_if_needed(result, text)
    except Exception:
        logger.exception("Failed to answer question")
        say("Sorry, I encountered an error while processing your question.")


def start() -> None:
    """Start the Slack bot using Socket Mode."""
    global _bot_user_id_resolved

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting Synapse backend in Socket Mode ...")

    if not _bot_user_id_resolved:
        try:
            auth = app.client.auth_test()
            settings.slack_bot_user_id = auth.get("user_id", "")
            _bot_user_id_resolved = True
        except Exception:
            logger.warning("Could not resolve bot user ID at startup")

    handler = SocketModeHandler(app, settings.slack_app_token)
    handler.start()


if __name__ == "__main__":
    start()