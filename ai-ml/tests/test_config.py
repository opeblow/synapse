"""Tests for the config module."""

from importlib import reload

import pytest

import synapse_ai.config as config_mod
from synapse_ai.config import Settings


def test_settings_load_from_env(monkeypatch):
    """Required keys are read from environment and surfaced correctly."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    monkeypatch.setenv("BRAVE_API_KEY", "bs-test-456")

    reload(config_mod)

    assert config_mod.settings.openai_api_key == "sk-test-123"
    assert config_mod.settings.brave_api_key == "bs-test-456"
    assert config_mod.settings.openai_model == "gpt-4o-mini"
    assert config_mod.settings.openai_embedding_model == "text-embedding-3-small"


def test_settings_missing_required_key_raises():
    """Constructing Settings without a required key raises a clear error."""
    with pytest.raises(Exception) as excinfo:
        Settings(openai_api_key="", brave_api_key="bs-test-456")

    assert "openai_api_key" in str(excinfo.value) or "field required" in str(excinfo.value)


def test_settings_defaults(monkeypatch):
    """Optional fields fall back to documented defaults."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    monkeypatch.setenv("BRAVE_API_KEY", "bs-test-456")

    reload(config_mod)

    s = config_mod.settings
    assert s.openai_timeout_seconds == 30
    assert s.openai_max_retries == 3
    assert s.brave_search_timeout_seconds == 15
    assert s.brave_search_max_retries == 2
    from pathlib import Path

    expected = str(Path(__file__).resolve().parent.parent / "chroma_data")
    assert s.chroma_persist_directory == expected
