"""Retrieval layer combining embedding and vector search.

This is the primary seam the backend will call to retrieve relevant
context chunks for a user question.
"""

from __future__ import annotations

import logging
from typing import Callable

from synapse_ai.clients.openai_client import OpenAIClient
from synapse_ai.vectorstore.store import ScoredChunk, VectorStore

logger = logging.getLogger(__name__)


class Retriever:
    """Wires an embedding model to a local vector store for retrieval.

    Usage::

        retriever = Retriever()
        retriever.add_documents([Document("some text", {"source": "doc1"})])
        chunks = retriever.retrieve("user question", k=5)
    """

    def __init__(
        self,
        embed_fn: Callable[[list[str]], list[list[float]]] | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        """Initialise the retriever.

        Args:
            embed_fn: Optional callable for generating embeddings.
                Defaults to ``OpenAIClient().embed``.
            vector_store: Optional pre-configured vector store.
                Defaults to a new :class:`VectorStore` using *embed_fn*.

        """
        if embed_fn is None:
            embed_fn = OpenAIClient().embed
        self._embed_fn = embed_fn

        if vector_store is not None:
            self._store = vector_store
        else:
            self._store = VectorStore(embed_fn=self._embed_fn)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_documents(self, documents: list) -> None:
        """Index a list of documents for retrieval.

        Args:
            documents: Iterable of :class:`Document` instances.

        """
        self._store.add(documents)
        logger.info("Indexed %d documents", len(documents))

    def retrieve(self, question: str, k: int = 5) -> list[ScoredChunk]:
        """Retrieve the *k* most relevant chunks for a question.

        Args:
            question: The user's question string.
            k: Number of chunks to return.

        Returns:
            A list of :class:`ScoredChunk` instances ordered by
            relevance (highest score first).

        """
        logger.info("Retrieving top-%d chunks for: %.100s", k, question)
        return self._store.query(question, k=k)

    @property
    def store(self) -> VectorStore:
        """The underlying vector store (useful for inspection in tests)."""
        return self._store
