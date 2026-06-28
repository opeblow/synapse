"""Tests for the FastAPI /internal/answer endpoint.

No real OpenAI / Brave / GitHub / RTS calls are made — all external
dependencies are mocked at the Python level.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from synapse_backend.api import app

client = TestClient(app)


class TestHealth:
    """GET /health returns a basic uptime check."""

    def test_ok(self) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestInternalAnswer:
    """POST /internal/answer"""

    def test_successful_answer(self, mocker) -> None:
        """Orchestrator returns a valid answer -> 200 with expected shape."""
        from synapse_ai.agent.orchestrator import AnswerResult, Source

        fake_result = AnswerResult(
            answer_markdown="**Hello**, world!",
            confidence="high",
            sources=[
                Source(title="Example", url="https://example.com", snippet="An example page"),
            ],
            decision_detected=False,
        )

        mock_orch = mocker.MagicMock()
        mock_orch.answer.return_value = fake_result
        mocker.patch("synapse_backend.api.get_orchestrator", return_value=mock_orch)

        resp = client.post("/internal/answer", json={"question": "Hello?"})
        assert resp.status_code == 200

        body = resp.json()
        assert body["answer_markdown"] == "**Hello**, world!"
        assert body["confidence"] == "high"
        assert body["decision_detected"] is False

        assert len(body["sources"]) == 1
        src = body["sources"][0]
        assert src["type"] == "web"
        assert src["title"] == "Example"
        assert src["url"] == "https://example.com"
        assert src["snippet"] == "An example page"
        assert src["timestamp"] == ""

    def test_successful_answer_decision_detected(self, mocker) -> None:
        """When decision_detected is True, the response reflects it."""
        from synapse_ai.agent.orchestrator import AnswerResult, Source

        fake_result = AnswerResult(
            answer_markdown="Approve the PR.",
            confidence="high",
            sources=[],
            decision_detected=True,
        )

        mock_orch = mocker.MagicMock()
        mock_orch.answer.return_value = fake_result
        mocker.patch("synapse_backend.api.get_orchestrator", return_value=mock_orch)

        resp = client.post("/internal/answer", json={"question": "Should I approve?"})
        assert resp.status_code == 200
        assert resp.json()["decision_detected"] is True

    def test_sources_include_correct_type(self, mocker) -> None:
        """Source type from the orchestrator propagates through the API response."""
        from synapse_ai.agent.orchestrator import AnswerResult, Source

        fake_result = AnswerResult(
            answer_markdown="Check GitHub.",
            confidence="medium",
            sources=[
                Source(title="org/repo: deploy.md", url="https://github.com/org/repo/deploy.md", snippet="Deploy script", type="github"),
                Source(title="# dev - Alice", url="https://slack.com/archives/C123/p123", snippet="Check the deploy script", type="slack_thread"),
            ],
            decision_detected=False,
        )

        mock_orch = mocker.MagicMock()
        mock_orch.answer.return_value = fake_result
        mocker.patch("synapse_backend.api.get_orchestrator", return_value=mock_orch)

        resp = client.post("/internal/answer", json={"question": "deploy?"})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["sources"]) == 2
        assert body["sources"][0]["type"] == "github"
        assert body["sources"][1]["type"] == "slack_thread"

    def test_orchestrator_exception_returns_500(self, mocker) -> None:
        """Orchestrator raising an Exception -> 500 with a message, no crash."""
        mock_orch = mocker.MagicMock()
        mock_orch.answer.side_effect = RuntimeError("Something went wrong")
        mocker.patch("synapse_backend.api.get_orchestrator", return_value=mock_orch)

        resp = client.post("/internal/answer", json={"question": "Fail?"})
        assert resp.status_code == 500
        body = resp.json()
        assert "detail" in body
        assert "Something went wrong" in body["detail"]
