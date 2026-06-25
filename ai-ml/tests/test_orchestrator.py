"""Tests for the orchestrator."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from synapse_ai.agent.orchestrator import AnswerResult, Orchestrator, Source
from synapse_ai.clients.brave_search_client import SearchResult
from synapse_ai.config import settings
from synapse_ai.vectorstore.store import ScoredChunk

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def mock_components():
    """Return an Orchestrator with all dependencies mocked.

    Yields ``(orchestrator, retriever, brave, llm, github)``.
    The ``github`` mock is a ``MagicMock`` that will never be called
    unless a test explicitly sets it up (``github_repo`` is empty at
    the module level by default).
    """
    retriever = MagicMock()
    brave = MagicMock()
    llm = MagicMock()
    github = MagicMock()
    orch = Orchestrator(
        retriever=retriever,
        brave_client=brave,
        openai_client=llm,
        github_client=github,
    )
    return orch, retriever, brave, llm, github


def _chunk(text: str, score: float, metadata: dict | None = None) -> ScoredChunk:
    return ScoredChunk(
        id="x",
        text=text,
        metadata=metadata or {"source": "doc"},
        score=score,
    )


# ------------------------------------------------------------------
# Tests: retrieval-only path (high confidence)
# ------------------------------------------------------------------


def test_retrieval_only_path(mock_components):
    """Top vector score >= 0.70 → answer from vector store, no web call."""
    orch, retriever, brave, llm, _ = mock_components
    retriever.retrieve.return_value = [
        _chunk("Deploy on Friday", 0.92, {"source": "policy.md"}),
        _chunk("Use CI pipeline", 0.85),
    ]
    llm.complete.return_value = "The deployment policy says to deploy on Friday."

    result = orch.answer("What is the deployment policy?")

    assert isinstance(result, AnswerResult)
    assert result.answer_markdown == "The deployment policy says to deploy on Friday."
    assert result.confidence == "high"
    assert len(result.sources) == 2
    assert result.sources[0].title == "policy.md"
    assert result.decision_detected is False

    # Brave should NOT be called for high-confidence retrieval
    brave.search.assert_not_called()


# ------------------------------------------------------------------
# Tests: fallback-to-search path (medium confidence)
# ------------------------------------------------------------------


def test_fallback_to_web_search(mock_components):
    """Top vector score < 0.70 but >= 0.35 → merge vector + web results."""
    orch, retriever, brave, llm, _ = mock_components
    retriever.retrieve.return_value = [
        _chunk("Somewhat relevant", 0.45, {"source": "internal"}),
    ]
    brave.search.return_value = [
        SearchResult(title="Web Result", url="https://example.com", snippet="Found online"),
    ]
    llm.complete.return_value = "Here's what I found from both sources."

    result = orch.answer("deployment policy")

    assert result.confidence == "medium"
    assert len(result.sources) == 2
    brave.search.assert_called_once()


def test_web_search_error_is_graceful(mock_components):
    """If Brave search raises, orchestrator should still return vector results."""
    orch, retriever, brave, llm, _ = mock_components
    retriever.retrieve.return_value = [
        _chunk("Internal note about policy", 0.50),
    ]
    brave.search.side_effect = Exception("Brave down")
    llm.complete.return_value = "Answer from internal docs only."

    result = orch.answer("policy")

    assert len(result.sources) == 1
    assert result.sources[0].title == "doc"
    assert result.confidence == "medium"


# ------------------------------------------------------------------
# Tests: no-good-match path (low confidence)
# ------------------------------------------------------------------


def test_no_good_match_no_vector_results(mock_components):
    """No vector results and no web results → 'I don't know' answer."""
    orch, retriever, brave, llm, _ = mock_components
    retriever.retrieve.return_value = []
    brave.search.return_value = []

    result = orch.answer("unknown topic")

    assert result.confidence == "low"
    assert "couldn't find" in result.answer_markdown.lower()
    assert result.sources == []


def test_no_good_match_low_vector_score_no_web(mock_components):
    """Low vector score (< 0.35) and no web results → 'I don't know'."""
    orch, retriever, brave, llm, _ = mock_components
    retriever.retrieve.return_value = [
        _chunk("Unrelated text", 0.10),
    ]
    brave.search.return_value = []

    result = orch.answer("unknown topic")

    assert result.confidence == "low"
    assert "couldn't find" in result.answer_markdown.lower()
    # Vector chunks with score < 0.35 are not included as sources
    assert result.sources == []


# ------------------------------------------------------------------
# Tests: decision detection
# ------------------------------------------------------------------


def test_decision_detection_with_transcript(mock_components):
    """When a transcript is provided, decision_signal is populated."""
    orch, retriever, brave, llm, _ = mock_components
    retriever.retrieve.return_value = [
        _chunk("Relevant info", 0.80),
    ]
    llm.complete.side_effect = [
        "Answer text",
        '{"is_decision": true, "summary": "Deploy Friday", "confidence": 0.9}',
    ]

    result = orch.answer("deploy?", conversation_transcript="A: deploy friday?\nB: yes")

    assert result.decision_detected is True
    assert result.decision_signal is not None
    assert result.decision_signal.is_decision is True
    assert result.decision_signal.summary == "Deploy Friday"
    assert result.decision_signal.confidence == 0.9


def test_decision_detection_no_transcript(mock_components):
    """Without a transcript, decision_signal is None."""
    orch, retriever, brave, llm, _ = mock_components
    retriever.retrieve.return_value = [
        _chunk("Info", 0.80),
    ]
    llm.complete.return_value = "Answer."

    result = orch.answer("question", conversation_transcript=None)

    assert result.decision_detected is False
    assert result.decision_signal is None


# ------------------------------------------------------------------
# Tests: sources deduplication
# ------------------------------------------------------------------


def test_sources_deduplicated_by_url(mock_components):
    """When the same URL appears in vector metadata and web results, deduplicate."""
    orch, retriever, brave, llm, _ = mock_components
    retriever.retrieve.return_value = [
        _chunk(
            "Internal doc",
            0.50,
            {"source": "internal", "url": "https://example.com/doc"},
        ),
    ]
    brave.search.return_value = [
        SearchResult(title="Web copy", url="https://example.com/doc", snippet="Same doc"),
    ]
    llm.complete.return_value = "Answer."

    result = orch.answer("question")

    # Only one source for the duplicate URL
    urls = [s.url for s in result.sources]
    assert urls.count("https://example.com/doc") == 1


# ------------------------------------------------------------------
# Tests: GitHub search integration
# ------------------------------------------------------------------


def test_github_results_merged_with_brave(monkeypatch):
    """GitHub results appear alongside Brave results when both return data."""
    monkeypatch.setattr(settings, "github_repo", "test/repo")
    retriever = MagicMock()
    brave = MagicMock()
    llm = MagicMock()
    github = MagicMock()
    orch = Orchestrator(
        retriever=retriever, brave_client=brave, openai_client=llm, github_client=github
    )

    retriever.retrieve.return_value = [_chunk("medium relevant", 0.45)]
    brave.search.return_value = [
        SearchResult(title="Brave Hit", url="https://brave.example.com", snippet="Brave snippet"),
    ]
    github.search.return_value = [
        Source(title="org/repo: file.py", url="https://github.com/org/repo/file.py", snippet="def foo"),
    ]
    llm.complete.return_value = "Answer."

    result = orch.answer("test query")

    assert len(result.sources) == 3  # vector + Brave + GitHub
    urls = [s.url for s in result.sources]
    assert "https://brave.example.com" in urls
    assert "https://github.com/org/repo/file.py" in urls
    brave.search.assert_called_once()
    github.search.assert_called_once()


def test_github_empty_brave_still_works(monkeypatch):
    """When GitHub returns nothing, Brave-only answer is unaffected."""
    monkeypatch.setattr(settings, "github_repo", "test/repo")
    retriever = MagicMock()
    brave = MagicMock()
    llm = MagicMock()
    github = MagicMock()
    orch = Orchestrator(
        retriever=retriever, brave_client=brave, openai_client=llm, github_client=github
    )

    retriever.retrieve.return_value = [_chunk("medium relevant", 0.45)]
    brave.search.return_value = [
        SearchResult(title="Brave Hit", url="https://brave.example.com", snippet="Brave snippet"),
    ]
    github.search.return_value = []
    llm.complete.return_value = "Answer."

    result = orch.answer("test query")

    assert len(result.sources) == 2  # vector + Brave
    assert result.sources[1].url == "https://brave.example.com"
    brave.search.assert_called_once()
    github.search.assert_called_once()


def test_github_exception_brave_still_works(monkeypatch):
    """When GitHub search raises, Brave results are still returned."""
    monkeypatch.setattr(settings, "github_repo", "test/repo")
    retriever = MagicMock()
    brave = MagicMock()
    llm = MagicMock()
    github = MagicMock()
    orch = Orchestrator(
        retriever=retriever, brave_client=brave, openai_client=llm, github_client=github
    )

    retriever.retrieve.return_value = [_chunk("medium relevant", 0.45)]
    brave.search.return_value = [
        SearchResult(title="Brave Hit", url="https://brave.example.com", snippet="Brave snippet"),
    ]
    github.search.side_effect = Exception("GitHub API down")
    llm.complete.return_value = "Answer."

    result = orch.answer("test query")

    assert len(result.sources) == 2  # vector + Brave, no GitHub
    assert result.sources[1].url == "https://brave.example.com"
    brave.search.assert_called_once()
    github.search.assert_called_once()


# ------------------------------------------------------------------
# Tests: RTS search integration
# ------------------------------------------------------------------


def test_rts_results_merged_with_brave_and_github(monkeypatch):
    """RTS results appear alongside Brave and GitHub when all return data."""
    monkeypatch.setattr(settings, "github_repo", "test/repo")
    retriever = MagicMock()
    brave = MagicMock()
    llm = MagicMock()
    github = MagicMock()
    rts = MagicMock()
    orch = Orchestrator(
        retriever=retriever,
        brave_client=brave,
        openai_client=llm,
        github_client=github,
        rts_client=rts,
    )

    retriever.retrieve.return_value = [_chunk("medium relevant", 0.45)]
    rts.search.return_value = [
        Source(
            title="# general - Alice",
            url="https://slack.com/archives/C123/p123",
            snippet="Deploy on Friday",
        ),
    ]
    brave.search.return_value = [
        SearchResult(
            title="Brave Hit",
            url="https://brave.example.com",
            snippet="Brave snippet",
        ),
    ]
    github.search.return_value = [
        Source(
            title="org/repo: file.py",
            url="https://github.com/org/repo/file.py",
            snippet="def foo",
        ),
    ]
    llm.complete.return_value = "Answer."

    result = orch.answer("test query")

    assert len(result.sources) == 4  # vector + RTS + Brave + GitHub
    urls = [s.url for s in result.sources]
    assert "https://slack.com/archives/C123/p123" in urls
    assert "https://brave.example.com" in urls
    assert "https://github.com/org/repo/file.py" in urls
    rts.search.assert_called_once()
    brave.search.assert_called_once()
    github.search.assert_called_once()


def test_rts_empty_brave_and_github_still_work(monkeypatch):
    """When RTS returns nothing, Brave and GitHub results are still included."""
    monkeypatch.setattr(settings, "github_repo", "test/repo")
    retriever = MagicMock()
    brave = MagicMock()
    llm = MagicMock()
    github = MagicMock()
    rts = MagicMock()
    orch = Orchestrator(
        retriever=retriever,
        brave_client=brave,
        openai_client=llm,
        github_client=github,
        rts_client=rts,
    )

    retriever.retrieve.return_value = [_chunk("medium relevant", 0.45)]
    rts.search.return_value = []
    brave.search.return_value = [
        SearchResult(
            title="Brave Hit",
            url="https://brave.example.com",
            snippet="Brave snippet",
        ),
    ]
    github.search.return_value = [
        Source(
            title="org/repo: file.py",
            url="https://github.com/org/repo/file.py",
            snippet="def foo",
        ),
    ]
    llm.complete.return_value = "Answer."

    result = orch.answer("test query")

    assert len(result.sources) == 3  # vector + Brave + GitHub
    assert result.sources[1].url == "https://brave.example.com"
    rts.search.assert_called_once()
    brave.search.assert_called_once()
    github.search.assert_called_once()


def test_rts_exception_brave_and_github_still_work(monkeypatch):
    """When RTS search raises, Brave and GitHub results are still returned."""
    monkeypatch.setattr(settings, "github_repo", "test/repo")
    retriever = MagicMock()
    brave = MagicMock()
    llm = MagicMock()
    github = MagicMock()
    rts = MagicMock()
    orch = Orchestrator(
        retriever=retriever,
        brave_client=brave,
        openai_client=llm,
        github_client=github,
        rts_client=rts,
    )

    retriever.retrieve.return_value = [_chunk("medium relevant", 0.45)]
    rts.search.side_effect = Exception("RTS API down")
    brave.search.return_value = [
        SearchResult(
            title="Brave Hit",
            url="https://brave.example.com",
            snippet="Brave snippet",
        ),
    ]
    github.search.return_value = [
        Source(
            title="org/repo: file.py",
            url="https://github.com/org/repo/file.py",
            snippet="def foo",
        ),
    ]
    llm.complete.return_value = "Answer."

    result = orch.answer("test query")

    assert len(result.sources) == 3  # vector + Brave + GitHub, no RTS
    assert result.sources[1].url == "https://brave.example.com"
    rts.search.assert_called_once()
    brave.search.assert_called_once()
    github.search.assert_called_once()
