"""Tests for the retrieval layer."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from synapse_ai.retrieval.retriever import Retriever
from synapse_ai.vectorstore.store import Document, ScoredChunk

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def mock_embed_fn():
    """Build a mock embedding function returning fixed-size vectors."""
    return MagicMock(return_value=[[0.1, 0.2, 0.3]])


@pytest.fixture
def mock_store():
    """Build a fully mocked vector store with canned results."""
    store = MagicMock()
    store.query.return_value = [
        ScoredChunk(id="1", text="chunk a", metadata={"src": "doc1"}, score=0.95),
        ScoredChunk(id="2", text="chunk b", metadata={"src": "doc2"}, score=0.80),
    ]
    return store


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


def test_retrieve_queries_store(mock_embed_fn, mock_store):
    r = Retriever(embed_fn=mock_embed_fn, vector_store=mock_store)
    results = r.retrieve("what is the policy?", k=3)

    mock_store.query.assert_called_once_with("what is the policy?", k=3)
    assert len(results) == 2
    assert results[0].text == "chunk a"
    assert results[1].score == 0.80


def test_add_documents_calls_store_add(mock_embed_fn, mock_store):
    r = Retriever(embed_fn=mock_embed_fn, vector_store=mock_store)
    docs = [Document("hello", {"tag": "greeting"})]
    r.add_documents(docs)

    mock_store.add.assert_called_once_with(docs)


def test_default_embed_fn_uses_openai():
    """When no embed_fn is provided, the constructor should not crash.

    The actual OpenAI client will be created but not called.
    """
    r = Retriever()
    assert r._embed_fn is not None


def test_retrieve_empty_store(mock_embed_fn, mock_store):
    mock_store.query.return_value = []
    r = Retriever(embed_fn=mock_embed_fn, vector_store=mock_store)

    results = r.retrieve("anything", k=5)
    assert results == []


def test_store_property(mock_embed_fn, mock_store):
    r = Retriever(embed_fn=mock_embed_fn, vector_store=mock_store)
    assert r.store is mock_store
