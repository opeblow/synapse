"""Tests for the decision classifier."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from synapse_ai.agent.decision_classifier import DecisionClassifier

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def mock_client():
    """Return a DecisionClassifier whose OpenAIClient is fully mocked."""
    client = MagicMock()
    classifier = DecisionClassifier(client=client)
    return classifier, client


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


def test_decision_detected(mock_client):
    classifier, mock_llm = mock_client
    mock_llm.complete.return_value = (
        '{"is_decision": true, "summary": "Deploy on Friday", "confidence": 0.95}'
    )

    signal = classifier.analyse("User A: Let's deploy on Friday\nUser B: Agreed.")

    assert signal.is_decision is True
    assert signal.summary == "Deploy on Friday"
    assert signal.confidence == 0.95


def test_no_decision(mock_client):
    classifier, mock_llm = mock_client
    mock_llm.complete.return_value = '{"is_decision": false, "summary": null, "confidence": 0.85}'

    signal = classifier.analyse("User A: What do you think?\nUser B: Not sure yet.")

    assert signal.is_decision is False
    assert signal.summary is None
    assert signal.confidence == 0.85


def test_malformed_json_raises(mock_client):
    classifier, mock_llm = mock_client
    mock_llm.complete.return_value = "not valid json at all"

    with pytest.raises(ValueError, match="Failed to parse"):
        classifier.analyse("Some conversation")


def test_json_with_markdown_fence(mock_client):
    classifier, mock_llm = mock_client
    mock_llm.complete.return_value = (
        "```json\n"
        '{"is_decision": true, "summary": "Go with option B", "confidence": 0.90}\n'
        "```"
    )

    signal = classifier.analyse("A: Option B sounds best.\nB: OK let's do it.")

    assert signal.is_decision is True
    assert signal.summary == "Go with option B"


def test_empty_summary(mock_client):
    classifier, mock_llm = mock_client
    mock_llm.complete.return_value = '{"is_decision": true, "summary": "", "confidence": 0.7}'

    signal = classifier.analyse("Let's do X.")

    assert signal.is_decision is True
    assert signal.summary == ""


def test_confidence_clamped(mock_client):
    classifier, mock_llm = mock_client
    mock_llm.complete.return_value = '{"is_decision": true, "summary": "OK", "confidence": 1.5}'

    signal = classifier.analyse("test")
    assert signal.confidence == 1.0

    mock_llm.complete.return_value = '{"is_decision": true, "summary": "OK", "confidence": -0.5}'
    signal = classifier.analyse("test")
    assert signal.confidence == 0.0


def test_calls_complete_with_correct_args(mock_client):
    classifier, mock_llm = mock_client
    mock_llm.complete.return_value = '{"is_decision": false, "summary": null, "confidence": 0.0}'

    transcript = "Hello world"
    classifier.analyse(transcript, temperature=0.1, max_tokens=100)

    mock_llm.complete.assert_called_once()
    args, kwargs = mock_llm.complete.call_args
    messages = args[0]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == transcript
    assert kwargs["temperature"] == 0.1
    assert kwargs["max_tokens"] == 100
