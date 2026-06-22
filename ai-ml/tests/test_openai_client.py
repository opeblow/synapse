"""Tests for the OpenAI client wrapper."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from openai import APIStatusError, APITimeoutError

from synapse_ai.clients.openai_client import (
    CompletionError,
    EmbeddingError,
    OpenAIClient,
)

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def client():
    """Return an OpenAIClient whose underlying SDK is fully mocked."""
    with patch("synapse_ai.clients.openai_client.OpenAI") as mock_sdk:
        instance = MagicMock()
        mock_sdk.return_value = instance
        yield OpenAIClient(), instance


# ------------------------------------------------------------------
# Embedding tests
# ------------------------------------------------------------------


def test_embed_success(client):
    oc, mock_instance = client
    fake_data = [
        MagicMock(embedding=[0.1, 0.2, 0.3]),
        MagicMock(embedding=[0.4, 0.5, 0.6]),
    ]
    mock_instance.embeddings.create.return_value = MagicMock(data=fake_data)

    result = oc.embed(["hello", "world"])

    assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    mock_instance.embeddings.create.assert_called_once_with(
        input=["hello", "world"], model="text-embedding-3-small"
    )


def test_embed_timeout(client):
    oc, mock_instance = client
    mock_instance.embeddings.create.side_effect = APITimeoutError("timeout")

    with pytest.raises(EmbeddingError, match="timed out"):
        oc.embed(["hello"])


def test_embed_api_status_error(client):
    oc, mock_instance = client
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_instance.embeddings.create.side_effect = APIStatusError(
        message="rate limited", response=mock_response, body=None
    )

    with pytest.raises(EmbeddingError, match="status 429"):
        oc.embed(["hello"])


def test_embed_empty_data(client):
    oc, mock_instance = client
    mock_instance.embeddings.create.return_value = MagicMock(data=[])

    with pytest.raises(EmbeddingError, match="no data"):
        oc.embed(["hello"])


# ------------------------------------------------------------------
# Chat completion tests
# ------------------------------------------------------------------


def test_complete_success(client):
    oc, mock_instance = client
    fake_msg = MagicMock()
    fake_msg.message.content = "Hello there!"
    mock_instance.chat.completions.create.return_value = MagicMock(choices=[fake_msg])

    result = oc.complete([{"role": "user", "content": "Hi"}])

    assert result == "Hello there!"
    mock_instance.chat.completions.create.assert_called_once_with(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hi"}],
    )


def test_complete_timeout(client):
    oc, mock_instance = client
    mock_instance.chat.completions.create.side_effect = APITimeoutError("timeout")

    with pytest.raises(CompletionError, match="timed out"):
        oc.complete([{"role": "user", "content": "Hi"}])


def test_complete_api_status_error(client):
    oc, mock_instance = client
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_instance.chat.completions.create.side_effect = APIStatusError(
        message="server error", response=mock_response, body=None
    )

    with pytest.raises(CompletionError, match="status 500"):
        oc.complete([{"role": "user", "content": "Hi"}])


def test_complete_no_choices(client):
    oc, mock_instance = client
    mock_instance.chat.completions.create.return_value = MagicMock(choices=[])

    with pytest.raises(CompletionError, match="no choices"):
        oc.complete([{"role": "user", "content": "Hi"}])


def test_complete_no_content(client):
    oc, mock_instance = client
    fake_msg = MagicMock()
    fake_msg.message.content = None
    mock_instance.chat.completions.create.return_value = MagicMock(choices=[fake_msg])

    with pytest.raises(CompletionError, match="no content"):
        oc.complete([{"role": "user", "content": "Hi"}])


# ------------------------------------------------------------------
# Live integration tests (skipped unless RUN_LIVE_TESTS=1)
# ------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1",
    reason="Set RUN_LIVE_TESTS=1 to run live API calls",
)
def test_live_embed():
    oc = OpenAIClient()
    result = oc.embed(["Hello world"])
    assert len(result) == 1
    assert len(result[0]) > 0
    assert all(isinstance(v, float) for v in result[0])


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1",
    reason="Set RUN_LIVE_TESTS=1 to run live API calls",
)
def test_live_complete():
    oc = OpenAIClient()
    result = oc.complete(
        [{"role": "user", "content": "Say exactly: pass"}],
        temperature=0,
        max_tokens=10,
    )
    assert isinstance(result, str)
    assert len(result) > 0
