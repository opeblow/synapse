"""Command-line interface for the Synapse AI/ML module.

Usage::

    # Seed the vector store with sample documents
    python -m synapse_ai.cli seed

    # Ask a question
    python -m synapse_ai.cli ask "What is the deployment policy?"

    # Ask with conversation transcript for decision detection
    python -m synapse_ai.cli ask "What did the team decide?" --transcript "..."

    # Use a custom number of results
    python -m synapse_ai.cli ask "How do I deploy?" --top-k 3

This is the one place where real API calls (OpenAI, Brave Search) are
expected and intentional.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from synapse_ai.agent.orchestrator import Orchestrator
from synapse_ai.clients.openai_client import OpenAIClient
from synapse_ai.retrieval.retriever import Retriever
from synapse_ai.vectorstore.store import Document, VectorStore

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"
SAMPLE_DOCS_PATH = FIXTURES_DIR / "sample_docs.json"


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s  %(message)s",
        stream=sys.stderr,
    )


# ------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------


def cmd_seed(args: argparse.Namespace) -> None:
    """Load sample documents into the vector store."""
    _setup_logging(args.verbose)

    if not SAMPLE_DOCS_PATH.exists():
        sys.stderr.write(f"ERROR: Sample docs not found at {SAMPLE_DOCS_PATH}\n")
        sys.exit(1)

    with SAMPLE_DOCS_PATH.open("r", encoding="utf-8") as f:
        records = json.load(f)

    client = OpenAIClient()
    store = VectorStore(embed_fn=client.embed)
    docs = [Document(r["text"], r.get("metadata", {})) for r in records]
    store.add(docs)
    store.persist()

    print(f"Seeded {len(docs)} documents into the vector store.")


def cmd_ask(args: argparse.Namespace) -> None:
    """Answer a question using the orchestrator."""
    _setup_logging(args.verbose)

    client = OpenAIClient()
    retriever = Retriever(embed_fn=client.embed)
    orch = Orchestrator(retriever=retriever, openai_client=client)

    result = orch.answer(
        args.question,
        conversation_transcript=args.transcript,
    )

    # Print the answer
    print()
    print(result.answer_markdown)
    print()

    # Print confidence
    print(f"Confidence: {result.confidence}")
    print()

    # Print sources
    if result.sources:
        print("Sources:")
        for i, src in enumerate(result.sources, 1):
            url_part = f" ({src.url})" if src.url else ""
            print(f"  {i}. {src.title}{url_part}")
            if src.snippet:
                print(f"     {src.snippet[:120]}...")
        print()

    # Print decision detection
    if result.decision_detected:
        print("[DECISION DETECTED] Decision detected in conversation.")
    else:
        print("[NO DECISION] No decision detected.")


# ------------------------------------------------------------------
# Argument parser
# ------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with ``seed`` and ``ask`` subcommands."""
    parser = argparse.ArgumentParser(
        prog="synapse-ai",
        description="Synapse AI/ML module — RAG Q&A and decision detection.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # seed
    seed_parser = subparsers.add_parser("seed", help="Seed the vector store with sample documents")
    seed_parser.set_defaults(func=cmd_seed)

    # ask
    ask_parser = subparsers.add_parser("ask", help="Ask a question")
    ask_parser.add_argument("question", type=str, help="Your question")
    ask_parser.add_argument(
        "--transcript",
        type=str,
        default=None,
        help="Conversation transcript for decision detection",
    )
    ask_parser.add_argument(
        "--top-k", type=int, default=5, help="Number of chunks to retrieve (default: 5)"
    )
    ask_parser.set_defaults(func=cmd_ask)

    return parser


def main() -> None:
    """Entry point: parse args and dispatch to the chosen subcommand."""
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
