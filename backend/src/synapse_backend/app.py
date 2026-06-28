"""Bolt application entry point for Synapse Slack bot."""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env into os.environ BEFORE any Settings class is imported,
# so both synapse_backend.config.settings and synapse_ai.config.settings
# read the same values regardless of process CWD.
_BACKEND_ENV = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_BACKEND_ENV)

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from synapse_ai.agent.orchestrator import AnswerResult

from synapse_backend.config import settings
from synapse_backend.orchestrator import ensure_vector_store_seeded, get_orchestrator
from synapse_backend.views import answer_message_view, decision_card_view

logger = logging.getLogger(__name__)

# Lazy: resolved inside start() so the module can be imported without a live Slack API call
_bot_user_id_resolved = False


def _post_decision_card_if_needed(app: App, result: AnswerResult, question: str) -> None:
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


# ── Health server (for Render Web Service) ──────────────────────────────


class _HealthHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler — Render's health check probe."""

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args) -> None:
        logger.debug("Health server: %s", format % args)


# ── Slack app builder (called inside start() after token validation) ────


def _build_app() -> App:
    """Create and configure the Slack Bolt App with event handlers."""
    app = App(token=settings.slack_bot_token, signing_secret=settings.slack_signing_secret)

    @app.event("message")
    def handle_message(event: dict, say) -> None:
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            return
        if event.get("channel_type") != "im":
            return

        text = event.get("text", "")
        logger.info("Received DM: %s", text)

        try:
            result = get_orchestrator().answer(text, conversation_transcript=text)
            say(blocks=answer_message_view(result), text=result.answer_markdown)
            _post_decision_card_if_needed(app, result, text)
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
            result = get_orchestrator().answer(text, conversation_transcript=text)
            say(blocks=answer_message_view(result), text=result.answer_markdown)
            _post_decision_card_if_needed(app, result, text)
        except Exception:
            logger.exception("Failed to answer question")
            say("Sorry, I encountered an error while processing your question.")

    return app


def start() -> None:
    """Start the Slack bot (Socket Mode) alongside a health HTTP server."""
    global _bot_user_id_resolved

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # ── Validate Slack credentials before touching the Slack API ────────
    missing: list[str] = []
    if not settings.slack_bot_token:
        missing.append("SLACK_BOT_TOKEN")
    if not settings.slack_app_token:
        missing.append("SLACK_APP_TOKEN")
    if not settings.slack_signing_secret:
        missing.append("SLACK_SIGNING_SECRET")
    if missing:
        for var in missing:
            logger.error("%s is empty — set it in your environment or .env file", var)
        sys.exit(1)

    ensure_vector_store_seeded()

    app = _build_app()

    if not _bot_user_id_resolved:
        try:
            auth = app.client.auth_test()
            settings.slack_bot_user_id = auth.get("user_id", "")
            _bot_user_id_resolved = True
        except Exception:
            logger.warning("Could not resolve bot user ID at startup")

    # Run Socket Mode in a background daemon thread
    handler = SocketModeHandler(app, settings.slack_app_token)
    socket_thread = threading.Thread(target=handler.start, daemon=True, name="socket-mode")
    socket_thread.start()
    logger.info("Socket Mode handler started in background thread")

    # Health HTTP server in the main thread (what Render probes)
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    logger.info("Health server listening on 0.0.0.0:%s", port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down ...")
        server.shutdown()


if __name__ == "__main__":
    start()
