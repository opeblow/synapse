"""Pytest configuration: set placeholder env vars so Settings() can load during import."""

from __future__ import annotations

import os


def pytest_configure() -> None:
    """Ensure required env vars exist before any module imports Settings."""
    os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test-bot-token")
    os.environ.setdefault("SLACK_APP_TOKEN", "xapp-test-app-token")
    os.environ.setdefault("SLACK_SIGNING_SECRET", "test-signing-secret")
