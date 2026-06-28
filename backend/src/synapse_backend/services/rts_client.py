"""Thin client wrapper around the Slack Real-Time Search (RTS) API.

Provides methods for searching across a Slack workspace (messages, files,
channels, users) using the ``assistant.search.context`` method — NOT the
legacy ``search.messages`` / ``search.all`` methods.

Requires a **user token** (``xoxp-...``) with the ``search:read.public``
and ``search:read.im`` scopes.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from synapse_ai.agent.orchestrator import Source
from synapse_backend.config import Settings
from synapse_backend.config import settings as _default_settings


_STOPWORDS = frozenset(
    {
        "a", "an", "the",
        "is", "are", "was", "were", "be", "been", "being",
        "it", "its",
        "and", "or", "but",
    }
)


def _normalize(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    import re

    return re.sub(r"[^\w\s]", "", s).lower().strip()


def _is_near_duplicate(text: str, query: str) -> bool:
    t = _normalize(text)
    q = _normalize(query)
    if not t or not q:
        return False
    # Exact match after normalisation
    if t == q:
        return True
    # Word-set overlap on non-stopword tokens.
    #
    # Stopwords (articles, auxiliary verbs, conjunctions) are excluded
    # first so that questions like "What is the deployment policy?" and
    # "What is the on-call policy?" aren't falsely conflated — without
    # this filter they share 4/5 words (what/is/the/policy) even though
    # the actual content words differ (deployment vs on/call).
    t_words = [w for w in t.split() if w not in _STOPWORDS]
    q_words = [w for w in q.split() if w not in _STOPWORDS]
    shorter_words, longer_words = (
        (t_words, q_words) if len(t_words) <= len(q_words) else (q_words, t_words)
    )
    if len(shorter_words) < 2:
        return False
    shorter_set = set(shorter_words)
    longer_set = set(longer_words)
    # For very short word lists (< 3) require exact content-word match;
    # for longer lists use the 80 % overlap threshold.  This prevents a
    # 2-word query like "deployment policy" from being absorbed by a
    # longer message like "Update the deployment policy" (100 % overlap
    # on the query's words, yet clearly a different intent).
    if len(shorter_words) < 3:
        return shorter_set == longer_set
    return len(shorter_set & longer_set) / len(shorter_set) >= 0.8

logger = logging.getLogger(__name__)

BASE_URL = "https://slack.com/api/assistant.search.context"

# ------------------------------------------------------------------
# Exceptions
# ------------------------------------------------------------------


class RTSSearchError(Exception):
    """Base exception for RTS client errors."""


class RTSSearchTimeoutError(RTSSearchError):
    """Raised when a search request times out after all retries are exhausted."""


class RTSSearchHTTPError(RTSSearchError):
    """Raised when the API returns a persistent non-2xx status or Slack returns ``ok``: ``false``."""


# ------------------------------------------------------------------
# Client
# ------------------------------------------------------------------


class RTSClient:
    """Wraps the Slack ``assistant.search.context`` endpoint.

    Results are returned as ``Source`` instances (from
    :mod:`synapse_ai.agent.orchestrator`) so they slot directly into
    the orchestrator without an adapter layer.

    Usage::

        client = RTSClient()
        results = client.search("deployment policy")
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
        self._token = cfg.slack_user_token
        self._timeout = timeout
        self._max_retries = max_retries
        self._bot_user_id = cfg.slack_bot_user_id
        self._client = httpx.Client(timeout=self._timeout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(self, query: str) -> list[Source]:
        """Search Slack workspace messages, files, channels, and users.

        Calls ``assistant.search.context`` — NOT the legacy
        ``search.messages`` or ``search.all`` endpoints.

        Args:
            query: The search query string.

        Returns:
            A list of :class:`~synapse_ai.agent.orchestrator.Source` instances.

        Raises:
            RTSSearchTimeoutError: If every retry attempt timed out.
            RTSSearchHTTPError: If the API returns a persistent non-2xx
                status or Slack returns ``"ok": false``.
        """
        headers = self._build_headers()
        body: dict[str, Any] = {
            "query": query,
            "channel_types": "public_channel,im",
            "content_types": "messages,files,channels,users",
        }

        last_exc: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = self._client.post(BASE_URL, json=body, headers=headers)
            except httpx.TimeoutException as exc:
                logger.warning(
                    "RTS search attempt %d/%d timed out", attempt, self._max_retries
                )
                last_exc = exc
                if attempt < self._max_retries:
                    self._sleep(attempt)
                continue

            if response.status_code >= 500 and attempt < self._max_retries:
                logger.warning(
                    "RTS search server error %d (attempt %d/%d), backing off",
                    response.status_code,
                    attempt,
                    self._max_retries,
                )
                last_exc = RTSSearchHTTPError(
                    f"Server error: HTTP {response.status_code}"
                )
                self._sleep(attempt)
                continue

            if not response.is_success:
                msg = (
                    f"RTS search returned HTTP {response.status_code}: "
                    f"{response.text[:200]}"
                )
                logger.warning(msg)
                raise RTSSearchHTTPError(msg)

            return self._parse_response(response.json(), query, self._bot_user_id)

        if isinstance(last_exc, httpx.TimeoutException):
            raise RTSSearchTimeoutError(
                f"RTS search timed out after {self._max_retries} attempts"
            ) from last_exc
        raise RTSSearchHTTPError(
            f"RTS search failed after {self._max_retries} attempts"
        ) from last_exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json; charset=utf-8",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    @staticmethod
    def _parse_response(
        data: dict[str, Any],
        query: str = "",
        bot_user_id: str = "",
    ) -> list[Source]:
        if not data.get("ok"):
            error = data.get("error", "unknown_error")
            logger.warning("Slack API returned ok=false: %s", error)
            raise RTSSearchHTTPError(f"Slack API error: {error}")

        results = data.get("results")
        if not isinstance(results, dict):
            logger.warning("RTS response missing 'results' dict: %.200s", json.dumps(data))
            return []

        sources: list[Source] = []

        for item in results.get("messages", []):
            if not isinstance(item, dict):
                continue

            # Filter out messages authored by the bot itself
            author_id = item.get("author_user_id", "")
            if bot_user_id and author_id == bot_user_id:
                continue

            content = item.get("content", "")
            # Filter out messages whose text is near-identical to the query
            if query and _is_near_duplicate(content, query):
                continue

            channel_name = item.get("channel_name", "")
            author_name = item.get("author_name", "")
            title = f"{channel_name} - {author_name}".strip(" -")
            url = item.get("permalink", "")
            snippet = content
            sources.append(Source(title=title, url=url, snippet=snippet, type="slack_thread"))

        for item in results.get("files", []):
            if not isinstance(item, dict):
                continue
            title = item.get("name", item.get("title", ""))
            url = item.get("permalink", "")
            snippet = item.get("title", "")
            sources.append(Source(title=title, url=url, snippet=snippet, type="slack_thread"))

        for item in results.get("channels", []):
            if not isinstance(item, dict):
                continue
            channel_name = item.get("name", "")
            raw_purpose = item.get("purpose", "")
            if isinstance(raw_purpose, dict):
                snippet = raw_purpose.get("value", "")
            else:
                snippet = str(raw_purpose) if raw_purpose else ""
            sources.append(Source(title=f"# {channel_name}", url="", snippet=snippet, type="slack_thread"))

        for item in results.get("users", []):
            if not isinstance(item, dict):
                continue
            real_name = item.get("real_name", "")
            display_name = item.get("display_name", "")
            name = item.get("name", "")
            title = real_name or display_name or name
            snippet = item.get("title", "")
            sources.append(Source(title=title, url="", snippet=snippet, type="slack_thread"))

        return sources

    @staticmethod
    def _sleep(attempt: int) -> None:
        import time

        delay = min(2 ** (attempt - 1), 30)
        time.sleep(delay)
