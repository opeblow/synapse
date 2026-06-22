"""Thin client wrapper around the Brave Search API.

Provides typed web-search calls with explicit timeouts, retries
with exponential backoff, and custom typed exceptions.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from synapse_ai.config import Settings
from synapse_ai.config import settings as _default_settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.search.brave.com/res/v1/web/search"


@dataclass
class SearchResult:
    """A single web-search result from Brave."""

    title: str
    url: str
    snippet: str


class BraveSearchError(Exception):
    """Base exception for Brave Search client errors."""


class BraveSearchTimeoutError(BraveSearchError):
    """Raised when a search request times out."""


class BraveSearchHTTPError(BraveSearchError):
    """Raised when the API returns a non-2xx status."""


class BraveSearchClient:
    """Wraps the Brave Search web API.

    Usage::

        client = BraveSearchClient()
        results = client.search("deployment policy")
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialise the client with an optional ``Settings`` override."""
        cfg = settings or _default_settings
        self._api_key = cfg.brave_api_key
        self._timeout = cfg.brave_search_timeout_seconds
        self._max_retries = cfg.brave_search_max_retries
        self._client = httpx.Client(timeout=self._timeout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(self, query: str, count: int = 10) -> list[SearchResult]:
        """Run a web search and return typed results.

        The request is retried with exponential backoff on transient
        failures (timeouts, 5xx status codes).

        Args:
            query: The search query string.
            count: Maximum number of results to return (1-20).

        Returns:
            A list of :class:`SearchResult` instances.

        Raises:
            BraveSearchTimeoutError: If every retry attempt timed out.
            BraveSearchHTTPError: If the API returns a persistent non-2xx
                status (including 4xx client errors).

        """
        params: dict[str, Any] = {"q": query, "count": min(count, 20)}
        url = f"{BASE_URL}?{urlencode(params)}"
        headers = {
            "X-Subscription-Token": self._api_key,
            "Accept": "application/json",
        }

        last_exc: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = self._client.get(url, headers=headers)
            except httpx.TimeoutException as exc:
                logger.warning("Brave search attempt %d/%d timed out", attempt, self._max_retries)
                last_exc = exc
                if attempt < self._max_retries:
                    self._sleep(attempt)
                continue

            if response.status_code == 429 and attempt < self._max_retries:
                logger.warning(
                    "Brave search rate-limited (attempt %d/%d), backing off",
                    attempt,
                    self._max_retries,
                )
                last_exc = BraveSearchHTTPError("Rate limited (429)")
                self._sleep(attempt)
                continue

            if response.status_code >= 500 and attempt < self._max_retries:
                logger.warning(
                    "Brave search server error %d (attempt %d/%d), backing off",
                    response.status_code,
                    attempt,
                    self._max_retries,
                )
                last_exc = BraveSearchHTTPError(f"Server error: {response.status_code}")
                self._sleep(attempt)
                continue

            if not response.is_success:
                msg = (
                    f"Brave search returned HTTP {response.status_code}: " f"{response.text[:200]}"
                )
                logger.warning(msg)
                raise BraveSearchHTTPError(msg)

            return self._parse_response(response.json())

        # All retries exhausted
        if isinstance(last_exc, httpx.TimeoutException):
            raise BraveSearchTimeoutError(
                f"Brave search timed out after {self._max_retries} attempts"
            ) from last_exc
        raise BraveSearchHTTPError(
            f"Brave search failed after {self._max_retries} attempts"
        ) from last_exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> list[SearchResult]:
        """Extract ``SearchResult`` items from the Brave API response."""
        web = data.get("web")
        if not web or not isinstance(web, dict):
            logger.warning("Brave response missing 'web' key: %.200s", json.dumps(data))
            return []

        results = web.get("results", [])
        if not isinstance(results, list):
            logger.warning("Brave 'web.results' is not a list: %.200s", json.dumps(data))
            return []

        parsed: list[SearchResult] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            title = item.get("title", "")
            url = item.get("url", "")
            snippet = item.get("description", "")
            if title or url:
                parsed.append(SearchResult(title=title, url=url, snippet=snippet))
        return parsed

    @staticmethod
    def _sleep(attempt: int) -> None:
        """Exponential backoff: 1s, 2s, 4s, … capped at 30s."""
        import time

        delay = min(2 ** (attempt - 1), 30)
        time.sleep(delay)
