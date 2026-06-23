"""Tests for the GitHub REST search client wrapper."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

from synapse_ai.agent.orchestrator import Source
from synapse_backend.services.github_mcp_client import (
    GitHubMCPClient,
    GitHubSearchHTTPError,
    GitHubSearchTimeoutError,
)

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def client():
    """Return a ``GitHubMCPClient`` whose underlying ``httpx.Client`` is mocked."""
    with patch(
        "synapse_backend.services.github_mcp_client.httpx.Client"
    ) as mock_httpx:
        instance = MagicMock()
        mock_httpx.return_value = instance
        yield GitHubMCPClient(), instance


SAMPLE_RESPONSE = {
    "total_count": 2,
    "items": [
        {
            "name": "deploy.md",
            "path": "docs/deploy.md",
            "html_url": "https://github.com/org/repo/blob/main/docs/deploy.md",
            "repository": {"full_name": "org/repo"},
            "text_matches": [
                {
                    "fragment": "Deploy on Friday after CI passes.",
                }
            ],
        },
        {
            "name": "README.md",
            "path": "README.md",
            "html_url": "https://github.com/org/repo/blob/main/README.md",
            "repository": {"full_name": "org/repo"},
            "text_matches": [
                {
                    "fragment": "Welcome to the deployment guide.",
                }
            ],
        },
    ],
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

    results = bs.search("deployment policy", repo="org/repo")

    assert len(results) == 2
    assert results[0] == Source(
        title="org/repo: docs/deploy.md",
        url="https://github.com/org/repo/blob/main/docs/deploy.md",
        snippet="Deploy on Friday after CI passes.",
    )
    assert results[1].title == "org/repo: README.md"
    assert results[1].snippet == "Welcome to the deployment guide."

    call_url = mock_httpx.get.call_args[0][0]
    assert "repo%3Aorg%2Frepo" in call_url
    assert "q=deployment+policy" in call_url or "q=deployment%20policy" in call_url


def test_search_without_repo(client):
    """Search without a repo filter should still work."""
    bs, mock_httpx = client
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"total_count": 0, "items": []}
    mock_httpx.get.return_value = mock_response

    results = bs.search("something")
    assert results == []


def test_search_empty_results(client):
    bs, mock_httpx = client
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"total_count": 0, "items": []}
    mock_httpx.get.return_value = mock_response

    results = bs.search("nothing")
    assert results == []


def test_search_missing_items_key(client):
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

    with pytest.raises(GitHubSearchTimeoutError, match="timed out after"):
        bs.search("query")


def test_search_5xx_then_retries_exhausted(client):
    bs, mock_httpx = client
    server_error = MagicMock()
    server_error.is_success = False
    server_error.status_code = 503
    server_error.text = "Service Unavailable"
    # One side-effect per retry attempt; with max_retries=3 we need 3
    mock_httpx.get.side_effect = [server_error, server_error, server_error]

    with patch(
        "synapse_backend.services.github_mcp_client.GitHubMCPClient._sleep"
    ):
        with pytest.raises(GitHubSearchHTTPError, match="HTTP 503"):
            bs.search("query")


def test_search_http_4xx_error(client):
    bs, mock_httpx = client
    mock_response = MagicMock()
    mock_response.is_success = False
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_httpx.get.return_value = mock_response

    with pytest.raises(GitHubSearchHTTPError, match="401"):
        bs.search("query")


def test_search_token_in_headers(client):
    """When a token is set, the Authorization header should be present."""
    bs, mock_httpx = client
    bs._token = "ghp_test123"
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"total_count": 0, "items": []}
    mock_httpx.get.return_value = mock_response

    bs.search("query")

    call_headers = mock_httpx.get.call_args[1]["headers"]
    assert call_headers["Authorization"] == "Bearer ghp_test123"


# ------------------------------------------------------------------
# Live integration test (skipped unless RUN_LIVE_TESTS=1)
# ------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1",
    reason="Set RUN_LIVE_TESTS=1 to run live API calls",
)
def test_live_search():
    """Real search against the public GitHub API (token loaded from Settings)."""
    client = GitHubMCPClient()
    results = client.search("README", repo="github/docs", per_page=3)
    assert len(results) > 0
    for r in results:
        assert isinstance(r, Source)
        assert r.title
        assert r.url
