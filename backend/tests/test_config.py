"""Tests for :mod:`synapse_backend.config`."""

from __future__ import annotations

import os

import pytest

from synapse_backend.config import Settings, settings


class TestSettingsDefaults:
    """Verify expected default values on the module-level instance."""

    def test_tokens_loaded(self) -> None:
        """The placeholder tokens from conftest should be present."""
        assert settings.slack_bot_token == "xoxb-test-bot-token"
        assert settings.slack_app_token == "xapp-test-app-token"
        assert settings.slack_signing_secret == "test-signing-secret"

    def test_default_log_level(self) -> None:
        """Default log level is INFO unless overridden."""
        assert settings.log_level == "INFO"

    def test_default_bot_user_id(self) -> None:
        """Bot user ID defaults to empty string."""
        assert settings.slack_bot_user_id == ""


class TestSettingsFromEnv:
    """Verify that env var overrides work correctly."""

    def test_custom_log_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        s = Settings()
        assert s.log_level == "DEBUG"

    def test_custom_bot_user_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SLACK_BOT_USER_ID", "U12345")
        s = Settings()
        assert s.slack_bot_user_id == "U12345"


class TestSettingsValidation:
    """Verify that missing required fields raise."""

    def test_missing_bot_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        with pytest.raises(ValueError, match="slack_bot_token"):
            Settings(_env_file=None)

    def test_missing_app_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SLACK_APP_TOKEN", raising=False)
        with pytest.raises(ValueError, match="slack_app_token"):
            Settings(_env_file=None)

    def test_missing_signing_secret_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)
        with pytest.raises(ValueError, match="slack_signing_secret"):
            Settings(_env_file=None)
