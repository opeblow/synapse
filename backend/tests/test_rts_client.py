"""Tests for the Slack RTS search client wrapper."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

from synapse_ai.agent.orchestrator import Source
from synapse_backend.services.rts_client import (
    RTSClient,
    RTSSearchHTTPError,
    RTSSearchTimeoutError,
)

# ------------------------------------------------------------------
# Sample responses
# ------------------------------------------------------------------

SAMPLE_SUCCESS = {
    "ok": True,
    "results": {
        "messages": [
            {
                "author_name": "Alice",
                "author_user_id": "U001",
                "team_id": "T001",
                "channel_id": "C123",
                "channel_name": "general",
                "message_ts": "1234567890.123456",
                "content": "Deploy on Friday after CI passes.",
                "is_author_bot": False,
                "permalink": "https://slack.com/archives/C123/p123",
            },
            {
                "author_name": "Bob",
                "author_user_id": "U002",
                "team_id": "T001",
                "channel_id": "C456",
                "channel_name": "dev",
                "message_ts": "1234567890.654321",
                "content": "Update the deployment policy.",
                "is_author_bot": False,
                "permalink": "https://slack.com/archives/C456/p456",
            },
        ],
        "files": [
            {
                "name": "deploy.pdf",
                "permalink": "https://slack.com/files/U789/F999/deploy.pdf",
                "title": "Deployment Guide",
            },
        ],
        "channels": [
            {
                "name": "proj-alpha",
                "purpose": {"value": "Channel for Project Alpha discussions"},
            },
        ],
        "users": [
            {
                "real_name": "Charlie Developer",
                "display_name": "charlied",
                "title": "Senior Engineer",
            },
        ],
    },
}


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def client():
    """Return an ``RTSClient`` whose underlying ``httpx.Client`` is mocked."""
    with patch("synapse_backend.services.rts_client.httpx.Client") as mock_httpx:
        instance = MagicMock()
        mock_httpx.return_value = instance
        yield RTSClient(), instance


# ------------------------------------------------------------------
# Search tests
# ------------------------------------------------------------------


def test_search_success(client):
    bs, mock_httpx = client
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_response.json.return_value = SAMPLE_SUCCESS
    mock_httpx.post.return_value = mock_response

    results = bs.search("deployment policy")

    assert len(results) == 5
    assert results[0] == Source(
        title="general - Alice",
        url="https://slack.com/archives/C123/p123",
        snippet="Deploy on Friday after CI passes.",
        type="slack_thread",
    )
    assert results[1].title == "dev - Bob"
    assert results[2].title == "deploy.pdf"
    assert results[3].title == "# proj-alpha"
    assert results[4].title == "Charlie Developer"

    call_url = mock_httpx.post.call_args[0][0]
    assert "assistant.search.context" in call_url
    call_body = mock_httpx.post.call_args[1]["json"]
    assert call_body["query"] == "deployment policy"
    assert call_body["channel_types"] == "public_channel,im"
    assert call_body["content_types"] == "messages,files,channels,users"
    call_headers = mock_httpx.post.call_args[1]["headers"]
    assert "Authorization" in call_headers
    assert call_headers["Authorization"].startswith("Bearer ")


def test_search_empty_results(client):
    bs, mock_httpx = client
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True, "results": {}}
    mock_httpx.post.return_value = mock_response

    results = bs.search("nothing")
    assert results == []


def test_search_empty_results_arrays(client):
    bs, mock_httpx = client
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "ok": True,
        "results": {"messages": [], "files": [], "channels": [], "users": []},
    }
    mock_httpx.post.return_value = mock_response

    results = bs.search("nothing")
    assert results == []


def test_search_malformed_missing_results_key(client):
    bs, mock_httpx = client
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True}
    mock_httpx.post.return_value = mock_response

    results = bs.search("nothing")
    assert results == []


def test_search_slack_error_ok_false(client):
    bs, mock_httpx = client
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "ok": False,
        "error": "missing_scope",
    }
    mock_httpx.post.return_value = mock_response

    with pytest.raises(RTSSearchHTTPError, match="missing_scope"):
        bs.search("query")


def test_search_timeout_then_retries_exhausted(client):
    bs, mock_httpx = client
    mock_httpx.post.side_effect = httpx.TimeoutException("timed out")

    with pytest.raises(RTSSearchTimeoutError, match="timed out after"):
        bs.search("query")


def test_search_5xx_then_retries_exhausted(client):
    bs, mock_httpx = client
    server_error = MagicMock()
    server_error.is_success = False
    server_error.status_code = 503
    server_error.text = "Service Unavailable"
    mock_httpx.post.side_effect = [server_error, server_error, server_error]

    with patch("synapse_backend.services.rts_client.RTSClient._sleep"):
        with pytest.raises(RTSSearchHTTPError, match="HTTP 503"):
            bs.search("query")


def test_search_http_4xx_error(client):
    bs, mock_httpx = client
    mock_response = MagicMock()
    mock_response.is_success = False
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_httpx.post.return_value = mock_response

    with pytest.raises(RTSSearchHTTPError, match="401"):
        bs.search("query")


def test_does_not_use_legacy_endpoints(client):
    """Verify the client calls ``assistant.search.context`` and NOT
    ``search.messages`` or ``search.all``."""
    bs, mock_httpx = client
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True, "results": {}}
    mock_httpx.post.return_value = mock_response

    bs.search("query")

    call_url = mock_httpx.post.call_args[0][0]
    assert "assistant.search.context" in call_url
    assert "search.messages" not in call_url
    assert "search.all" not in call_url


def test_timeout_then_recovers_on_retry(client):
    bs, mock_httpx = client
    timeout = httpx.TimeoutException("timed out")
    ok_response = MagicMock()
    ok_response.is_success = True
    ok_response.status_code = 200
    ok_response.json.return_value = SAMPLE_SUCCESS
    mock_httpx.post.side_effect = [timeout, ok_response]

    with patch("synapse_backend.services.rts_client.RTSClient._sleep"):
        results = bs.search("query")

    assert len(results) == 5


# ------------------------------------------------------------------
# Live integration test (skipped unless RUN_LIVE_TESTS=1)
# ------------------------------------------------------------------


# ------------------------------------------------------------------
# Tests: bot-message and near-duplicate filtering
# ------------------------------------------------------------------


def test_filters_out_bot_messages(client):
    """Messages authored by the bot (matching slack_bot_user_id) are excluded."""
    bs, mock_httpx = client
    bs._bot_user_id = "U999"
    payload = {
        "ok": True,
        "results": {
            "messages": [
                {
                    "author_name": "Synapse",
                    "author_user_id": "U999",
                    "team_id": "T001",
                    "channel_id": "C123",
                    "channel_name": "general",
                    "message_ts": "1000000000.000001",
                    "content": "I am a bot reply.",
                    "is_author_bot": True,
                    "permalink": "https://slack.com/archives/C123/p123",
                },
                {
                    "author_name": "Alice",
                    "author_user_id": "U001",
                    "team_id": "T001",
                    "channel_id": "C456",
                    "channel_name": "random",
                    "message_ts": "1000000000.000002",
                    "content": "What do you think?",
                    "is_author_bot": False,
                    "permalink": "https://slack.com/archives/C456/p456",
                },
            ],
        },
    }
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_response.json.return_value = payload
    mock_httpx.post.return_value = mock_response

    results = bs.search("question")
    assert len(results) == 1
    assert results[0].title == "random - Alice"





def test_filters_out_near_duplicate_messages(client):
    """Messages whose content is near-identical to the query are excluded."""
    bs, mock_httpx = client
    payload = {
        "ok": True,
        "results": {
            "messages": [
                {
                    "author_name": "Bob",
                    "author_user_id": "U002",
                    "team_id": "T001",
                    "channel_id": "C456",
                    "channel_name": "dev",
                    "message_ts": "1000000000.000001",
                    "content": "What is the deployment policy?",
                    "is_author_bot": False,
                    "permalink": "https://slack.com/archives/C456/p456",
                },
                {
                    "author_name": "Alice",
                    "author_user_id": "U001",
                    "team_id": "T001",
                    "channel_id": "C123",
                    "channel_name": "general",
                    "message_ts": "1000000000.000002",
                    "content": "Here is the deployment guide link.",
                    "is_author_bot": False,
                    "permalink": "https://slack.com/archives/C123/p123",
                },
            ],
        },
    }
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_response.json.return_value = payload
    mock_httpx.post.return_value = mock_response

    results = bs.search("What is the deployment policy?")
    assert len(results) == 1
    assert results[0].title == "general - Alice"


def test_filters_out_near_duplicate_missing_article(client):
    """Regression: query 'what is deployment policy?' should be filtered
    against 'What is the deployment policy?' (missing 'the' in the match)."""
    bs, mock_httpx = client
    payload = {
        "ok": True,
        "results": {
            "messages": [
                {
                    "author_name": "Bob",
                    "author_user_id": "U002",
                    "team_id": "T001",
                    "channel_id": "C456",
                    "channel_name": "dev",
                    "message_ts": "1000000000.000001",
                    "content": "what is deployment policy?",
                    "is_author_bot": False,
                    "permalink": "https://slack.com/archives/C456/p456",
                },
                {
                    "author_name": "Alice",
                    "author_user_id": "U001",
                    "team_id": "T001",
                    "channel_id": "C123",
                    "channel_name": "general",
                    "message_ts": "1000000000.000002",
                    "content": "Here is the deployment guide link.",
                    "is_author_bot": False,
                    "permalink": "https://slack.com/archives/C123/p123",
                },
            ],
        },
    }
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_response.json.return_value = payload
    mock_httpx.post.return_value = mock_response

    results = bs.search("What is the deployment policy?")
    assert len(results) == 1
    assert results[0].title == "general - Alice"


def test_does_not_filter_different_question_with_shared_stopwords(client):
    """Regression: 'What is the deployment policy?' and 'What is the on-call
    policy?' differ only in content words (deployment vs on/call) but share
    grammatical stopwords — must NOT be flagged as near-duplicates.

    Before the stopword-filter fix the overlap was 80 % (4/5 words:
    what/is/the/policy), which hit the default threshold and incorrectly
    suppressed the message.
    """
    bs, mock_httpx = client
    payload = {
        "ok": True,
        "results": {
            "messages": [
                {
                    "author_name": "Alice",
                    "author_user_id": "U001",
                    "team_id": "T001",
                    "channel_id": "C456",
                    "channel_name": "dev",
                    "message_ts": "1000000000.000001",
                    "content": "What is the on-call policy?",
                    "is_author_bot": False,
                    "permalink": "https://slack.com/archives/C456/p456",
                },
            ],
        },
    }
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_response.json.return_value = payload
    mock_httpx.post.return_value = mock_response

    results = bs.search("What is the deployment policy?")
    assert len(results) == 1
    assert results[0].title == "dev - Alice"


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1",
    reason="Set RUN_LIVE_TESTS=1 to run live API calls",
)
def test_live_search():
    """Real search against the Slack RTS API (token loaded from Settings)."""
    client = RTSClient()
    results = client.search("hello")
    assert len(results) > 0
    for r in results:
        assert isinstance(r, Source)
