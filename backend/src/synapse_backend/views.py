"""Block Kit view builders for Slack messages."""

from __future__ import annotations

from synapse_ai.agent.decision_classifier import DecisionSignal
from synapse_ai.agent.orchestrator import AnswerResult


def answer_message_view(result: AnswerResult) -> list[dict]:
    """Build Slack Block Kit blocks from an :class:`AnswerResult`.

    Returns a list of block dicts suitable for ``say(blocks=...)``.
    """
    blocks: list[dict] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": result.answer_markdown}},
    ]

    if not result.sources:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": ":warning:  No confident source found, so I won't guess."}],
        })
        return blocks

    blocks.append({"type": "divider"})

    conf = result.confidence or "medium"
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"*Sources \u00b7 {len(result.sources)}*    confidence: {conf}"}],
    })

    SOURCE_GLYPH = {
        "slack_thread": ":thread:",
        "google_drive": ":page_facing_up:",
        "github": ":octocat:",
        "notion": ":notebook:",
    }

    for s in result.sources:
        glyph = SOURCE_GLYPH.get(s.type, ":link:")
        section: dict = {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"{glyph}  *{s.title}*\n_{s.snippet}_"},
        }
        if s.url:
            section["accessory"] = {
                "type": "button",
                "text": {"type": "plain_text", "text": "View"},
                "url": s.url,
                "action_id": "view_source",
            }
        blocks.append(section)
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"{s.type} \u00b7 {getattr(s, 'date', '')}"}],
        })

    return blocks


def decision_card_view(
    signal: DecisionSignal,
    question: str,
    *,
    body: str = "",
    decided_by: str = "",
    channel: str = "",
    date: str = "",
    decision_id: str = "",
    thread_url: str = "",
) -> list[dict]:
    """Build a Slack Block Kit card for a detected decision."""
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": "Decision captured", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{signal.summary or 'No summary available'}*"}},
    ]
    if body:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": body}})
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"decided by {decided_by} \u00b7 {channel} \u00b7 {date}"}],
    })
    elements: list[dict] = [
        {"type": "button", "text": {"type": "plain_text", "text": "Confirm"}, "style": "primary", "action_id": "confirm_decision", "value": decision_id},
        {"type": "button", "text": {"type": "plain_text", "text": "Dispute"}, "style": "danger", "action_id": "dispute_decision", "value": decision_id},
    ]
    if thread_url:
        elements.insert(0, {"type": "button", "text": {"type": "plain_text", "text": "View thread"}, "url": thread_url, "action_id": "view_thread"})
    blocks.append({
        "type": "actions",
        "block_id": f"decision_{decision_id}",
        "elements": elements,
    })
    return blocks


def app_home_view(
    decisions: list[dict] | None = None,
    channels: list[dict] | None = None,
    first_run: bool = False,
) -> list[dict]:
    """Build the App Home tab."""
    decisions = decisions or []
    channels = channels or []
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": "Synapse", "emoji": True}},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Your workspace's memory. Ask a question and get the answer with its sources."},
            "accessory": {
                "type": "button", "text": {"type": "plain_text", "text": "Ask Synapse"},
                "style": "primary", "action_id": "open_ask_modal",
            },
        },
        {"type": "divider"},
    ]

    if first_run:
        blocks += [
            {"type": "header", "text": {"type": "plain_text", "text": "Get set up", "emoji": True}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "1.  Add Synapse to a channel\n2.  Connect Drive, Notion, or GitHub\n3.  Ask your first question"}},
        ]
        return blocks

    blocks.append({"type": "header", "text": {"type": "plain_text", "text": "Recent decisions", "emoji": True}})
    if not decisions:
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": "Nothing captured yet. Decisions show up here on their own."}]})
    else:
        for d in decisions[:5]:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{d.get('summary', '')}*"}})
            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"{d.get('decided_by', '')} \u00b7 {d.get('channel', '')} \u00b7 {d.get('date', '')}"}],
            })

    blocks += [
        {"type": "divider"},
        {"type": "header", "text": {"type": "plain_text", "text": "Indexing", "emoji": True}},
    ]
    for c in channels:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"*{c.get('name', '')}*  last indexed {c.get('last_indexed', '')}"}],
        })

    return blocks


def ask_modal_view() -> dict:
    """Build the Ask Synapse modal."""
    return {
        "type": "modal",
        "callback_id": "ask_modal_submit",
        "title": {"type": "plain_text", "text": "Ask Synapse"},
        "submit": {"type": "plain_text", "text": "Ask"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "question_block",
                "label": {"type": "plain_text", "text": "What do you want to know?"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "question_input",
                    "placeholder": {"type": "plain_text", "text": "Why did we move off Postgres for the events table?"},
                },
            },
        ],
    }
