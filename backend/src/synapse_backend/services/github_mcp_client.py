"""Thin client wrapper around the GitHub REST search API.

Provides methods for searching repository code/content with explicit
timeouts, retries with exponential backoff, and custom typed exceptions.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from synapse_ai.agent.orchestrator import Source
from synapse_backend.config import Settings
from synapse_backend.config import settings as _default_settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.github.com"

# ------------------------------------------------------------------
# Exceptions
# ------------------------------------------------------------------


class GitHubSearchError(Exception):
    """Base exception for GitHub Search client errors."""


class GitHubSearchTimeoutError(GitHubSearchError):
    """Raised when a search request times out after all retries are exhausted."""


class GitHubSearchHTTPError(GitHubSearchError):
    """Raised when the API returns a persistent non-2xx status."""


# ------------------------------------------------------------------
# Client
# ------------------------------------------------------------------


class GitHubMCPClient:
    """Wraps the GitHub REST search API for code/content search.

    Results are returned as ``Source`` instances (from
    :mod:`synapse_ai.agent.orchestrator`) so they can slot directly into
    the orchestrator without an adapter layer.

    Usage::

        client = GitHubMCPClient()
        results = client.search("deployment policy", repo="myorg/my-repo")
    """

    def __init__(
        self,
        settings: Settings | None = None,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        """Initialise the client with optional configuration overrides.

        Args:
            settings: A ``Settings`` instance (defaults to the module-level
                singleton).
            timeout: Timeout in seconds for each HTTP request.
            max_retries: How many times to retry on timeouts or 5xx errors.
        """
        cfg = settings or _default_settings
        self._token = cfg.github_token
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = httpx.Client(timeout=self._timeout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(self, query: str, repo: str | None = None, per_page: int = 10) -> list[Source]:
        """Search GitHub code matching *query*, optionally scoped to *repo*.

        Uses the ``/search/code`` endpoint.  Results are returned as a
        list of :class:`~synapse_ai.agent.orchestrator.Source` — the
        same shape used by the orchestrator's answer pipeline.

        Args:
            query: The search query.
            repo: Optional ``owner/repo`` string to scope the search.
            per_page: Number of results per page (max 100).

        Returns:
            A list of :class:`~synapse_ai.agent.orchestrator.Source` instances.

        Raises:
            GitHubSearchTimeoutError: If every retry attempt timed out.
            GitHubSearchHTTPError: If the API returns a persistent non-2xx
                status (including 4xx client errors).
        """
        q = query
        if repo:
            q = f"{q} repo:{repo}"

        params: dict[str, Any] = {"q": q, "per_page": min(per_page, 100)}
        url = f"{BASE_URL}/search/code?{urlencode(params)}"
        headers = self._build_headers()

        last_exc: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = self._client.get(url, headers=headers)
            except httpx.TimeoutException as exc:
                logger.warning(
                    "GitHub search attempt %d/%d timed out", attempt, self._max_retries
                )
                last_exc = exc
                if attempt < self._max_retries:
                    self._sleep(attempt)
                continue

            if response.status_code >= 500 and attempt < self._max_retries:
                logger.warning(
                    "GitHub search server error %d (attempt %d/%d), backing off",
                    response.status_code,
                    attempt,
                    self._max_retries,
                )
                last_exc = GitHubSearchHTTPError(
                    f"Server error: HTTP {response.status_code}"
                )
                self._sleep(attempt)
                continue

            if not response.is_success:
                msg = (
                    f"GitHub search returned HTTP {response.status_code}: "
                    f"{response.text[:200]}"
                )
                logger.warning(msg)
                raise GitHubSearchHTTPError(msg)

            return self._parse_response(response.json())

        # All retries exhausted
        if isinstance(last_exc, httpx.TimeoutException):
            raise GitHubSearchTimeoutError(
                f"GitHub search timed out after {self._max_retries} attempts"
            ) from last_exc
        raise GitHubSearchHTTPError(
            f"GitHub search failed after {self._max_retries} attempts"
        ) from last_exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_headers(self) -> dict[str, str]:
        """Build request headers, injecting the token if available."""
        headers: dict[str, str] = {
            "Accept": "application/vnd.github.v3.text-match+json",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> list[Source]:
        """Extract ``Source`` items from the GitHub search API response."""
        items = data.get("items", [])
        if not isinstance(items, list):
            logger.warning("GitHub response 'items' is not a list: %.200s", json.dumps(data))
            return []

        results: list[Source] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            name = item.get("name", "")
            path = item.get("path", "")
            html_url = item.get("html_url", "")

            repo_name = ""
            repo_obj = item.get("repository")
            if isinstance(repo_obj, dict):
                repo_name = repo_obj.get("full_name", "")

            snippet = ""
            text_matches = item.get("text_matches")
            if isinstance(text_matches, list) and text_matches:
                fragment = text_matches[0].get("fragment", "")
                if fragment:
                    snippet = fragment.strip()

            display_title = f"{repo_name}: {path}" if repo_name else name
            results.append(
                Source(title=display_title, url=html_url, snippet=snippet, type="github")
            )

        return results

    @staticmethod
    def _sleep(attempt: int) -> None:
        """Exponential backoff: 1s, 2s, 4s, … capped at 30s."""
        import time

        delay = min(2 ** (attempt - 1), 30)
        time.sleep(delay)
