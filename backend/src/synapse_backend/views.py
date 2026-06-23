"""Block Kit view builders for Slack messages."""

from __future__ import annotations

from synapse_ai.agent.decision_classifier import DecisionSignal
from synapse_ai.agent.orchestrator import AnswerResult


def answer_message_view(result: AnswerResult) -> list[dict]:
    """Build Slack Block Kit blocks from an :class:`AnswerResult`.

    Returns a list of block dicts suitable for ``say(blocks=...)``.
    """
    blocks: list[dict] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": result.answer_markdown,
            },
        },
    ]

    if result.sources:
        blocks.append({"type": "divider"})
        source_lines: list[str] = []
        for i, s in enumerate(result.sources, start=1):
            if s.url:
                source_lines.append(f"{i}. <{s.url}|{s.title}>")
            else:
                source_lines.append(f"{i}. {s.title}")
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "*Sources:*\n" + "\n".join(source_lines),
                    },
                ],
            },
        )

    return blocks


def decision_card_view(signal: DecisionSignal, question: str) -> list[dict]:
    """Build a Slack Block Kit card for a detected decision."""
    summary = signal.summary or "No summary available"
    confidence_pct = f"{signal.confidence:.0%}"

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Decision Detected"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Summary:*\n{summary}"},
                {"type": "mrkdwn", "text": f"*Confidence:*\n{confidence_pct}"},
            ],
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Triggered by: _{question}_"},
            ],
        },
    ]
    return blocks
