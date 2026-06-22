"""Smoke tests verifying the environment is wired correctly."""

from __future__ import annotations


class TestAiMlImport:
    """Confirm the ai-ml package is importable as an editable dependency."""

    def test_import_synapse_ai(self) -> None:
        """``import synapse_ai`` should succeed (editable install is wired)."""
        import synapse_ai  # noqa: F401

    def test_orchestrator_importable(self) -> None:
        """Key classes from ai-ml should be reachable."""
        from synapse_ai.agent.orchestrator import AnswerResult, Orchestrator, Source

        assert AnswerResult is not None
        assert Orchestrator is not None
        assert Source is not None

    def test_decision_classifier_importable(self) -> None:
        from synapse_ai.agent.decision_classifier import DecisionClassifier, DecisionSignal

        assert DecisionClassifier is not None
        assert DecisionSignal is not None
