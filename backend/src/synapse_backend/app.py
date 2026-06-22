"""Bolt application entry point for Synapse Slack bot."""

from __future__ import annotations

import logging

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from synapse_backend.config import settings

logger = logging.getLogger(__name__)

app = App(token=settings.slack_bot_token, signing_secret=settings.slack_signing_secret)


@app.event("message")
def handle_message(event: dict, say) -> None:
    """Respond to any direct message with a simple greeting.

    Args:
        event: The Slack event payload.
        say: A callable to post a message in the conversation.
    """
    logger.info("Received message event: %s", event.get("text", ""))
    say("Hello! I'm Synapse. Ask me anything.")

    # Store bot user ID on first event
    if bot_id := event.get("bot_id"):
        settings.slack_bot_user_id = bot_id
    elif user := app.client.auth_test():
        settings.slack_bot_user_id = user.get("user_id", "")


@app.event("app_mention")
def handle_mention(event: dict, say) -> None:
    """Respond when the bot is mentioned in a channel.

    Args:
        event: The Slack event payload.
        say: A callable to post a message in the conversation.
    """
    logger.info("Received mention: %s", event.get("text", ""))
    say("Hello! I'm Synapse. Ask me anything.")


def start() -> None:
    """Start the Slack bot using Socket Mode."""
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting Synapse backend in Socket Mode ...")
    handler = SocketModeHandler(app, settings.slack_app_token)
    handler.start()


if __name__ == "__main__":
    start()
