"""Thin client wrapper around the OpenAI API.

Provides typed methods for embeddings and chat completions with
explicit timeouts, retries, and custom typed exceptions.
"""

from __future__ import annotations

import logging
from typing import Any

from openai import APIError, APIStatusError, APITimeoutError, OpenAI

from synapse_ai.config import Settings
from synapse_ai.config import settings as _default_settings

logger = logging.getLogger(__name__)


class OpenAIError(Exception):
    """Base exception for all OpenAI client errors."""


class EmbeddingError(OpenAIError):
    """Raised when an embedding request fails after all retries."""


class CompletionError(OpenAIError):
    """Raised when a chat completion request fails after all retries."""


class OpenAIClient:
    """Wraps the OpenAI SDK for embedding and chat-completion calls.

    Usage::

        client = OpenAIClient()
        embedding = client.embed(["Hello world"])
        reply = client.complete([{"role": "user", "content": "Hi"}])
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialise the client with an optional ``Settings`` override."""
        cfg = settings or _default_settings
        self._settings = cfg
        self._client = OpenAI(
            api_key=cfg.openai_api_key,
            timeout=cfg.openai_timeout_seconds,
            max_retries=cfg.openai_max_retries,
        )

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Embed a list of texts into dense vector representations.

        Args:
            texts: One or more text strings to embed.
            model: Override the configured embedding model.

        Returns:
            A list of embedding vectors, one per input text.

        Raises:
            EmbeddingError: If the API call fails after all retries.

        """
        model = model or self._settings.openai_embedding_model
        try:
            response = self._client.embeddings.create(input=texts, model=model)
        except APITimeoutError as exc:
            msg = "Embedding request timed out"
            logger.warning("%s: %s", msg, exc)
            raise EmbeddingError(msg) from exc
        except APIStatusError as exc:
            msg = f"Embedding request failed with status {exc.status_code}"
            logger.warning("%s: %s", msg, exc)
            raise EmbeddingError(msg) from exc
        except APIError as exc:
            msg = "Embedding request failed"
            logger.warning("%s: %s", msg, exc)
            raise EmbeddingError(msg) from exc

        if not response.data:
            msg = "Embedding response contained no data"
            logger.warning(msg)
            raise EmbeddingError(msg)

        return [item.embedding for item in response.data]

    # ------------------------------------------------------------------
    # Chat completion
    # ------------------------------------------------------------------

    def complete(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Send a chat-completion request and return the reply text.

        Args:
            messages: Message history in OpenAI format
                (``[{"role": "user", "content": "..."}, ...]``).
            model: Override the configured chat model.
            **kwargs: Additional parameters forwarded to the SDK
                (e.g. ``temperature``, ``max_tokens``).

        Returns:
            The content of the assistant's reply.

        Raises:
            CompletionError: If the API call fails after all retries.

        """
        model = model or self._settings.openai_model
        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs,
            )
        except APITimeoutError as exc:
            msg = "Chat completion request timed out"
            logger.warning("%s: %s", msg, exc)
            raise CompletionError(msg) from exc
        except APIStatusError as exc:
            msg = f"Chat completion request failed with status {exc.status_code}"
            logger.warning("%s: %s", msg, exc)
            raise CompletionError(msg) from exc
        except APIError as exc:
            msg = "Chat completion request failed"
            logger.warning("%s: %s", msg, exc)
            raise CompletionError(msg) from exc

        choices = response.choices
        if not choices:
            msg = "Chat completion response contained no choices"
            logger.warning(msg)
            raise CompletionError(msg)

        content = choices[0].message.content
        if content is None:
            msg = "Chat completion response contained no content"
            logger.warning(msg)
            raise CompletionError(msg)

        return content
