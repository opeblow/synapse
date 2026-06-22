"""Tests for the vector store."""

from __future__ import annotations

import numpy as np
import pytest

from synapse_ai.vectorstore.store import Document, ScoredChunk, VectorStore

# ------------------------------------------------------------------
# Fake embedding function for tests
# ------------------------------------------------------------------


def _fake_embed(texts: list[str]) -> list[list[float]]:
    """Return a deterministic vector for each input text.

    Uses a simple hash so that identical texts get identical vectors
    and similar texts get nearby vectors (roughly).
    """
    rng = np.random.default_rng(seed=42)
    # Hash the concatenated texts to make results deterministic
    hashed = hash("|".join(texts))
    rng = np.random.default_rng(seed=abs(hashed))
    return rng.uniform(-1, 1, (len(texts), 4)).tolist()


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def store(tmp_path):
    """Return a VectorStore backed by a temp directory."""
    return VectorStore(
        embed_fn=_fake_embed,
        persist_directory=str(tmp_path),
        collection_name="test_collection",
    )


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


def test_add_and_count(store):
    docs = [
        Document("The sky is blue", {"source": "weather"}),
        Document("Grass is green", {"source": "nature"}),
    ]
    store.add(docs)
    assert store.count() == 2


def test_add_empty_does_nothing(store):
    store.add([])
    assert store.count() == 0


def test_query_returns_scored_chunks(store):
    docs = [
        Document("The sky is blue and clear", {"source": "weather"}),
        Document("Grass is green in spring", {"source": "nature"}),
        Document("Python is a programming language", {"source": "tech"}),
    ]
    store.add(docs)

    results = store.query("sky weather", k=2)

    assert len(results) == 2
    for r in results:
        assert isinstance(r, ScoredChunk)
        assert r.id
        assert r.text
        assert isinstance(r.metadata, dict)
        assert -1.0 <= r.score <= 1.0


def test_query_returns_correct_fields(store):
    docs = [
        Document("Machine learning is fun", {"category": "ai"}),
    ]
    store.add(docs)

    results = store.query("machine learning", k=1)
    assert len(results) == 1
    r = results[0]
    assert r.text == "Machine learning is fun"
    assert r.metadata == {"category": "ai"}


def test_query_k_greater_than_docs(store):
    docs = [
        Document("Only one document here", {"id": 1}),
    ]
    store.add(docs)

    results = store.query("document", k=10)
    assert len(results) == 1


def test_delete_collection(store):
    store.add([Document("Hello", {})])
    assert store.count() == 1

    store.delete_collection()
    assert store.count() == 0
    assert store.query("hello", k=5) == []


def test_multiple_add_batches(store):
    store.add([Document("First batch", {"batch": 1})])
    store.add([Document("Second batch", {"batch": 2})])
    assert store.count() == 2


def test_persist_and_reload(tmp_path):
    """Data should survive a store close/reload cycle."""
    store1 = VectorStore(
        embed_fn=_fake_embed,
        persist_directory=str(tmp_path),
        collection_name="persist_test",
    )
    store1.add([Document("Hello world", {"src": "test"})])
    store1.persist()

    store2 = VectorStore(
        embed_fn=_fake_embed,
        persist_directory=str(tmp_path),
        collection_name="persist_test",
    )
    assert store2.count() == 1
    results = store2.query("hello", k=1)
    assert len(results) == 1
    assert results[0].text == "Hello world"


def test_query_returns_sorted_by_score(store):
    """Results should be ordered by descending similarity score."""
    docs = [
        Document("alpha", {"id": 1}),
        Document("beta", {"id": 2}),
        Document("gamma", {"id": 3}),
    ]
    store.add(docs)

    results = store.query("alpha", k=3)
    assert len(results) == 3
    for i in range(len(results) - 1):
        assert results[i].score >= results[i + 1].score
