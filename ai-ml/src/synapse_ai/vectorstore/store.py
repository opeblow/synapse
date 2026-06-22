"""Local vector store — a pure-Python file-backed vector index.

Embeds documents externally (e.g. via OpenAIClient) and stores them in a
local HNSW-like index built on numpy for approximate nearest-neighbour search.
Persistence is handled through a simple JSON + numpy file format.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """A single document to be indexed in the vector store."""

    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class ScoredChunk:
    """A retrieved chunk with its similarity score."""

    id: str
    text: str
    metadata: dict
    score: float


class VectorStore:
    """File-backed vector index using numpy for similarity search.

    Embeddings are computed externally and passed to the store — it does
    not call any embedding API itself.

    Data is persisted as two sibling files under *persist_directory*:

      * ``vectors.npy`` — a numpy array of shape ``(N, D)``
      * ``documents.json`` — a JSON list of document records

    Usage::

        store = VectorStore(embed_fn=openai_client.embed)
        store.add([Document("some text", {"source": "doc1"})])
        results = store.query("my question", k=5)
    """

    def __init__(
        self,
        embed_fn: Callable[[list[str]], list[list[float]]],
        persist_directory: str = "./chroma_data",
        collection_name: str = "synapse_docs",
    ) -> None:
        """Initialise the store with an embedding function and persist path."""
        self._embed_fn = embed_fn
        self._collection_name = collection_name
        self._path = Path(persist_directory) / collection_name
        self._path.mkdir(parents=True, exist_ok=True)

        self._vec_path: Path = self._path / "vectors.npy"
        self._doc_path: Path = self._path / "documents.json"
        self._vectors: np.ndarray | None = None
        self._documents: list[dict] = []
        self._dirty: bool = False
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, documents: list[Document]) -> None:
        """Embed and store a batch of documents.

        Args:
            documents: One or more :class:`Document` instances to index.

        """
        if not documents:
            return

        texts = [d.text for d in documents]
        ids = [str(uuid.uuid4()) for _ in documents]
        metadatas = [d.metadata for d in documents]

        embeddings = self._embed_fn(texts)
        new_vecs = np.array(embeddings, dtype=np.float32)

        for i in range(len(documents)):
            self._documents.append({"id": ids[i], "text": texts[i], "metadata": metadatas[i]})

        if self._vectors is None:
            self._vectors = new_vecs
        else:
            self._vectors = np.concatenate([self._vectors, new_vecs], axis=0)

        self._dirty = True
        logger.info("Added %d documents (total %d)", len(documents), self.count())

    def query(self, text: str, k: int = 5) -> list[ScoredChunk]:
        """Retrieve the *k* most similar chunks for a query string.

        Similarity is measured via cosine distance on the embedding vectors.

        Args:
            text: The query text.
            k: Number of nearest neighbours to return.

        Returns:
            A list of :class:`ScoredChunk` instances ordered by
            descending similarity (highest score first).

        """
        if self._vectors is None or self._vectors.shape[0] == 0:
            return []

        query_vec = np.array(self._embed_fn([text])[0], dtype=np.float32).reshape(1, -1)

        # Cosine similarity: (A · B) / (||A|| * ||B||)
        norms = np.linalg.norm(self._vectors, axis=1, keepdims=True)
        query_norm = np.linalg.norm(query_vec)
        if norms.min() == 0 or query_norm == 0:
            return []

        similarities = (self._vectors @ query_vec.T).flatten() / (
            norms.flatten() * query_norm + 1e-10
        )

        # Top-k indices
        k = min(k, len(similarities))
        top_indices = np.argsort(similarities)[-k:][::-1]

        results: list[ScoredChunk] = []
        for idx in top_indices:
            doc = self._documents[idx]
            results.append(
                ScoredChunk(
                    id=doc["id"],
                    text=doc["text"],
                    metadata=doc["metadata"],
                    score=float(similarities[idx]),
                )
            )
        return results

    def count(self) -> int:
        """Return the number of documents currently indexed."""
        return len(self._documents)

    def delete_collection(self) -> None:
        """Remove the entire collection and all its data on disk."""
        self._vectors = None
        self._documents = []
        self._dirty = False

        if self._vec_path.exists():
            self._vec_path.unlink()
        if self._doc_path.exists():
            self._doc_path.unlink()

        try:
            self._path.rmdir()
        except OSError:
            pass

        logger.info("Deleted collection '%s'", self._collection_name)

    def persist(self) -> None:
        """Explicitly flush in-memory state to disk (also called on ``add``)."""
        self._save()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Restore state from disk if it exists."""
        if self._doc_path.exists() and self._vec_path.exists():
            try:
                with self._doc_path.open("r", encoding="utf-8") as f:
                    self._documents = json.load(f)
                self._vectors = np.load(str(self._vec_path))
                logger.info("Loaded %d documents from %s", len(self._documents), self._path)
            except (json.JSONDecodeError, OSError, ValueError) as exc:
                logger.warning("Failed to load persisted state: %s", exc)
                self._documents = []
                self._vectors = None

    def _save(self) -> None:
        """Write current state to disk."""
        if self._vectors is None:
            return
        np.save(str(self._vec_path), self._vectors)
        with self._doc_path.open("w", encoding="utf-8") as f:
            json.dump(self._documents, f, ensure_ascii=False)
        self._dirty = False
