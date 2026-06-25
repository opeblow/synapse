"""Orchestrator — routes a user question to the best available knowledge source.

Decides whether to answer from the local vector store, fall back to web
search, or reply "I don't know", and synthesises a cited markdown answer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from synapse_ai.agent.decision_classifier import DecisionSignal
from synapse_ai.clients.brave_search_client import BraveSearchClient, SearchResult
from synapse_ai.clients.openai_client import OpenAIClient
from synapse_ai.config import settings
from synapse_ai.retrieval.retriever import Retriever
from synapse_ai.vectorstore.store import ScoredChunk

logger = logging.getLogger(__name__)

# Similarity thresholds for routing decisions
HIGH_CONFIDENCE_THRESHOLD = 0.70
MEDIUM_CONFIDENCE_THRESHOLD = 0.35

ANSWER_SYSTEM_PROMPT = """\
You are a helpful assistant. Answer the user's question based on the context \
below. When you use information from a source, cite it by number in square \
brackets like [1], [2] etc.

If the provided context does not contain enough information to answer the \
question, say so clearly and do not make up an answer."""

NO_ANSWER_MESSAGE = "I'm sorry, I couldn't find any relevant information to answer your question."


@dataclass
class Source:
    """A single cited source for an answer."""

    title: str
    url: str = ""
    snippet: str = ""


@dataclass
class AnswerResult:
    """The final structured answer returned by the orchestrator.

    Matches the JSON contract the frontend expects.
    """

    answer_markdown: str
    confidence: str  # "high", "medium", or "low"
    sources: list[Source] = field(default_factory=list)
    decision_detected: bool = False
    decision_signal: DecisionSignal | None = None


class Orchestrator:
    """Routes questions to the best available knowledge provider.

    Usage::

        orchestrator = Orchestrator()
        result = orchestrator.answer("What is the deployment policy?")
    """

    def __init__(
        self,
        retriever: Retriever | None = None,
        brave_client: BraveSearchClient | None = None,
        openai_client: OpenAIClient | None = None,
        github_client: Any = None,
        rts_client: Any = None,
    ) -> None:
        """Initialise with optional pre-configured dependencies."""
        self._retriever = retriever or Retriever()
        self._brave = brave_client or BraveSearchClient()
        self._llm = openai_client or OpenAIClient()
        self._github = github_client
        self._github_repo = settings.github_repo
        self._rts = rts_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def answer(
        self,
        question: str,
        conversation_transcript: str | None = None,
        **llm_kwargs: Any,
    ) -> AnswerResult:
        """Answer a question using the best available knowledge source.

        The routing logic is:

        1. Retrieve chunks from the local vector store.
        2. If the top chunk scores above **0.70**, answer with high
           confidence from those chunks alone.
        3. If the top chunk scores above **0.35**, also fetch web
           results and merge both sources (medium confidence).
        4. Otherwise fall back to web search only.
        5. When an ``rts_client`` is configured and vector scores are
           below the high-confidence threshold, search the Slack workspace
           first (RTS) — it runs before Brave because internal Slack
           messages are the most directly relevant source.
        6. When a ``github_client`` is configured and vector scores are
           below the high-confidence threshold, also search GitHub code
           and merge results (after Brave, so a slow/empty GitHub
           response never blocks the primary fallback).
        7. If no relevant sources are found at all, return a
           "I don't know" answer (low confidence).

        Args:
            question: The user's question.
            conversation_transcript: Optional conversation context for
                decision detection.
            **llm_kwargs: Additional parameters for the LLM call
                (e.g. ``temperature``, ``max_tokens``).

        Returns:
            An :class:`AnswerResult` with the answer, sources, and
            confidence label.

        """
        llm_kwargs.setdefault("temperature", 0.0)
        llm_kwargs.setdefault("max_tokens", 512)

        # Step 1: retrieve from vector store
        vector_chunks = self._retriever.retrieve(question, k=5)

        best_score = vector_chunks[0].score if vector_chunks else 0.0
        logger.info("Top vector-store score for %r: %.3f", question[:80], best_score)

        # Step 2-4: decide on sources
        sources, context_text = self._gather_sources(question, vector_chunks, best_score)

        if not sources:
            signal = self._detect_decision(conversation_transcript)
            return AnswerResult(
                answer_markdown=NO_ANSWER_MESSAGE,
                confidence="low",
                sources=[],
                decision_detected=signal.is_decision if signal else False,
                decision_signal=signal,
            )

        # Synthesise answer from context
        confidence = self._confidence_label(best_score, bool(vector_chunks))
        answer = self._synthesise(question, context_text, **llm_kwargs)
        signal = self._detect_decision(conversation_transcript)

        return AnswerResult(
            answer_markdown=answer,
            confidence=confidence,
            sources=sources,
            decision_detected=signal.is_decision if signal else False,
            decision_signal=signal,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _gather_sources(
        self,
        question: str,
        vector_chunks: list[ScoredChunk],
        best_score: float,
    ) -> tuple[list[Source], str]:
        """Collect sources and build a context string.

        Returns ``(sources, context_text)``. Returns ``([], "")`` when
        no sources are found.
        """
        sources: list[Source] = []
        context_parts: list[str] = []
        idx = 1

        if best_score >= MEDIUM_CONFIDENCE_THRESHOLD:
            for chunk in vector_chunks:
                title = chunk.metadata.get("title", chunk.metadata.get("source", "Untitled"))
                url = chunk.metadata.get("url", "")
                sources.append(Source(title=title, url=url, snippet=chunk.text))
                context_parts.append(f"[{idx}] {title}\n{chunk.text}")
                idx += 1

        # If vector results are weak, fall back to search
        if best_score < HIGH_CONFIDENCE_THRESHOLD:
            # RTS — search our own Slack workspace first (most directly relevant)
            if self._rts is not None:
                try:
                    rts_results: list[Source] = self._rts.search(question)
                except Exception:
                    logger.warning("RTS search failed, continuing without it")
                    rts_results = []

                for result in rts_results:
                    if any(s.url == result.url for s in sources):
                        continue
                    sources.append(result)
                    title = result.title
                    snippet = result.snippet or "(no snippet)"
                    context_parts.append(f"[{idx}] {title}\n{snippet}")
                    idx += 1

            try:
                web_results: list[SearchResult] = self._brave.search(question, count=5)
            except Exception:
                logger.warning("Brave search failed, continuing with vector results only")
                web_results = []

            for result in web_results:
                # Avoid duplicates
                if any(s.url == result.url for s in sources):
                    continue
                sources.append(Source(title=result.title, url=result.url, snippet=result.snippet))
                context_parts.append(f"[{idx}] {result.title} ({result.url})\n{result.snippet}")
                idx += 1

            # Supplement with GitHub code search (after Brave so it never blocks)
            if self._github is not None and self._github_repo:
                try:
                    gh_results: list[Source] = self._github.search(
                        question, repo=self._github_repo, per_page=5
                    )
                except Exception:
                    logger.warning("GitHub search failed, continuing without it")
                    gh_results = []

                for result in gh_results:
                    if any(s.url == result.url for s in sources):
                        continue
                    sources.append(result)
                    title = result.title
                    snippet = result.snippet or "(no snippet)"
                    context_parts.append(f"[{idx}] {title}\n{snippet}")
                    idx += 1

        if not sources:
            return [], ""

        return sources, "\n\n".join(context_parts)

    def _synthesise(self, question: str, context: str, **llm_kwargs: Any) -> str:
        """Generate a markdown answer from the collected context."""
        messages = [
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}",
            },
        ]
        return self._llm.complete(messages, **llm_kwargs)

    def _detect_decision(self, transcript: str | None) -> DecisionSignal | None:
        """Optionally run decision detection on a conversation transcript."""
        if not transcript:
            return None
        try:
            from synapse_ai.agent.decision_classifier import DecisionClassifier

            classifier = DecisionClassifier(client=self._llm)
            return classifier.analyse(transcript)
        except Exception:
            logger.warning("Decision detection failed, skipping", exc_info=True)
            return None

    @staticmethod
    def _confidence_label(best_score: float, has_vector_results: bool) -> str:
        """Map the best similarity score to a confidence label."""
        if has_vector_results and best_score >= HIGH_CONFIDENCE_THRESHOLD:
            return "high"
        if best_score >= MEDIUM_CONFIDENCE_THRESHOLD:
            return "medium"
        return "low"
