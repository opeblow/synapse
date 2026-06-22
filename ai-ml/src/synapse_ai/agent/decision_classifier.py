"""Decision classifier — detects whether a conversation contains a decision.

Uses an LLM call with a structured prompt to analyse short transcripts and
return a typed signal.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from synapse_ai.clients.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a decision-detection assistant. Analyse the conversation transcript \
below and determine whether the participants reached a clear decision.

A decision is a definitive conclusion, agreement, or choice made by the group \
— e.g. "we'll go with option A", "let's deploy on Friday", \
"John will own the task". Mere discussion, questions, or brainstorming without \
closure is NOT a decision.

Respond with a JSON object (and nothing else) using exactly this schema:
{
    "is_decision": true or false,
    "summary": "Short phrase describing the decision, or null if no decision",
    "confidence": 0.0 to 1.0
}"""


@dataclass
class DecisionSignal:
    """The result of analysing a transcript for a decision.

    Attributes:
        is_decision: Whether a decision was detected.
        summary: A short human-readable summary of the decision, or
            ``None`` if no decision was found.
        confidence: A float between 0 and 1 indicating the model's
            confidence in its determination.

    """

    is_decision: bool
    summary: str | None
    confidence: float


class DecisionClassifier:
    """Classifies a short conversation transcript as decision or non-decision.

    Usage::

        classifier = DecisionClassifier()
        signal = classifier.analyse(transcript_string)
    """

    def __init__(self, client: OpenAIClient | None = None) -> None:
        """Initialise with an optional pre-configured ``OpenAIClient``."""
        self._client = client or OpenAIClient()

    def analyse(self, transcript: str, **kwargs: Any) -> DecisionSignal:
        """Analyse a transcript and return a decision signal.

        Args:
            transcript: The conversation text to analyse.
            **kwargs: Additional parameters forwarded to the chat completion
                call (e.g. ``temperature``, ``max_tokens``).

        Returns:
            A :class:`DecisionSignal` instance.

        Raises:
            ValueError: If the model response cannot be parsed as the
                expected JSON schema.

        """
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ]

        # Use low temperature for more deterministic output
        kwargs.setdefault("temperature", 0.0)
        kwargs.setdefault("max_tokens", 256)

        response = self._client.complete(messages, **kwargs)

        return self._parse_response(response)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(raw: str) -> DecisionSignal:
        """Parse the model's JSON response into a ``DecisionSignal``.

        Handles common formatting issues such as markdown code fences
        and trailing whitespace.
        """
        cleaned = raw.strip()

        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            first_nl = cleaned.find("\n")
            if first_nl != -1:
                cleaned = cleaned[first_nl + 1 :]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            msg = f"Failed to parse classifier output as JSON: {raw!r}"
            logger.warning(msg)
            raise ValueError(msg) from exc

        if not isinstance(data, dict):
            msg = f"Classifier output is not a JSON object: {raw!r}"
            logger.warning(msg)
            raise ValueError(msg)

        is_decision = bool(data.get("is_decision", False))
        summary = data.get("summary")
        if summary is not None and not isinstance(summary, str):
            summary = str(summary)
        confidence = float(data.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))

        return DecisionSignal(
            is_decision=is_decision,
            summary=summary,
            confidence=confidence,
        )
