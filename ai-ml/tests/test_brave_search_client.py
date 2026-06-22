"""Tests for the Brave Search client wrapper."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

from synapse_ai.clients.brave_search_client import (
    BraveSearchClient,
    BraveSearchHTTPError,
    BraveSearchTimeoutError,
    SearchResult,
)

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def client():
    """Return a BraveSearchClient whose underlying httpx.Client is mocked."""
    with patch("synapse_ai.clients.brave_search_client.httpx.Client") as mock_httpx:
        instance = MagicMock()
        mock_httpx.return_value = instance
        yield BraveSearchClient(), instance


SAMPLE_RESPONSE = {
    "web": {
        "results": [
            {
                "title": "Deployment Policy",
                "url": "https://example.com/deploy",
                "description": "Our deployment policy requires CI passes.",
            },
            {
                "title": "Second Result",
                "url": "https://example.com/second",
                "description": "A second search hit.",
            },
        ]
    }
}


# ------------------------------------------------------------------
# Search tests
# ------------------------------------------------------------------


def test_search_success(client):
    bs, mock_httpx = client
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_response.json.return_value = SAMPLE_RESPONSE
    mock_httpx.get.return_value = mock_response

    results = bs.search("deployment policy")

    assert len(results) == 2
    assert results[0] == SearchResult(
        title="Deployment Policy",
        url="https://example.com/deploy",
        snippet="Our deployment policy requires CI passes.",
    )
    assert results[1].title == "Second Result"

    call_url = mock_httpx.get.call_args[0][0]
    assert "q=deployment+policy" in call_url or "q=deployment%20policy" in call_url


def test_search_empty_results(client):
    bs, mock_httpx = client
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"web": {"results": []}}
    mock_httpx.get.return_value = mock_response

    results = bs.search("nothing")
    assert results == []


def test_search_missing_web_key(client):
    bs, mock_httpx = client
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_httpx.get.return_value = mock_response

    results = bs.search("nothing")
    assert results == []


def test_search_timeout_then_retries_exhausted(client):
    bs, mock_httpx = client
    mock_httpx.get.side_effect = httpx.TimeoutException("timed out")

    with pytest.raises(BraveSearchTimeoutError, match="timed out after"):
        bs.search("query")


def test_search_rate_limit_then_recovers(client):
    bs, mock_httpx = client
    rate_limited = MagicMock()
    rate_limited.is_success = False
    rate_limited.status_code = 429
    ok_response = MagicMock()
    ok_response.is_success = True
    ok_response.status_code = 200
    ok_response.json.return_value = SAMPLE_RESPONSE
    mock_httpx.get.side_effect = [rate_limited, ok_response]

    with patch("synapse_ai.clients.brave_search_client.BraveSearchClient._sleep"):
        results = bs.search("query")

    assert len(results) == 2


def test_search_http_4xx_error(client):
    bs, mock_httpx = client
    mock_response = MagicMock()
    mock_response.is_success = False
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_httpx.get.return_value = mock_response

    with pytest.raises(BraveSearchHTTPError, match="401"):
        bs.search("query")


def test_search_5xx_then_retries_exhausted(client):
    bs, mock_httpx = client
    server_error = MagicMock()
    server_error.is_success = False
    server_error.status_code = 503
    server_error.text = "Service Unavailable"
    mock_httpx.get.side_effect = [server_error, server_error]

    with patch("synapse_ai.clients.brave_search_client.BraveSearchClient._sleep"):
        with pytest.raises(BraveSearchHTTPError, match="HTTP 503"):
            bs.search("query")


# ------------------------------------------------------------------
# Live integration test (skipped unless RUN_LIVE_TESTS=1)
# ------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1",
    reason="Set RUN_LIVE_TESTS=1 to run live API calls",
)
def test_live_search():
    bs = BraveSearchClient()
    results = bs.search("hello world", count=3)
    assert len(results) > 0
    for r in results:
        assert isinstance(r, SearchResult)
        assert r.title
        assert r.url
