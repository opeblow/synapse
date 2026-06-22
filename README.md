<div align="center">

![Synapse AI Logo](./ai-ml/docs/logo.svg)

</div>

<div align="center">

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![License](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000?style=for-the-badge)](https://github.com/astral-sh/ruff)
[![Checked with black](https://img.shields.io/badge/code%20style-black-000000?style=for-the-badge)](https://github.com/psf/black)

</div>

# Synapse AI/ML Module

Self-contained AI module for the Synapse Slack agent. Provides:

- **Retrieval-augmented Q&A** — answer questions from a local vector store, with
  cited sources.
- **Decision detection** — classify short conversation transcripts as containing
  a decision or not.
- **Web search fallback** — when the local store lacks relevant information, fall
  back to Brave Search.

## Quick start

```bash
cd ai-ml
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e ".[dev]"
cp .env.example .env     # fill in your API keys
pytest
```

## CLI

```bash
# Seed the vector store with sample documents
python -m synapse_ai.cli seed

# Ask a question (uses vector store + optional web fallback)
python -m synapse_ai.cli ask "What is the team's deployment policy?"
```

## Project structure

```
ai-ml/
├── src/synapse_ai/
│   ├── clients/             # OpenAI & Brave Search wrappers
│   │   ├── openai_client.py
│   │   └── brave_search_client.py
│   ├── vectorstore/         # NumPy-backed local vector store (no Rust deps)
│   │   └── store.py         # VectorStore, Document, ScoredChunk
│   ├── retrieval/           # Retrieval pipeline
│   │   └── retriever.py     # Retriever (embed + query)
│   ├── agent/               # Decision classifier & orchestrator
│   │   ├── decision_classifier.py  # DecisionClassifier, DecisionSignal
│   │   └── orchestrator.py         # Orchestrator, AnswerResult
│   ├── config.py            # Settings from environment (pydantic-settings)
│   └── cli.py               # CLI entry point
├── tests/
│   ├── fixtures/
│   │   └── sample_docs.json # 8 sample documents for seeding
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_openai_client.py
│   ├── test_brave_search_client.py
│   ├── test_vectorstore.py
│   ├── test_retriever.py
│   ├── test_decision_classifier.py
│   └── test_orchestrator.py
├── pyproject.toml
└── README.md
```

## Architecture

```
User question
     │
     v
  Orchestrator ──> Retriever ──> VectorStore (NumPy)
     │                │                │
     │                v                v
     │          embed via          index.json +
     │         OpenAI API          vectors.npy
     │
     ├── confidence >= 0.70 ──> vector-store only answer
     ├── confidence >= 0.35 ──> vector + Brave Search
     └── confidence <  0.35 ──> Brave Search / "I don't know"

Decision detection runs in parallel on raw transcripts
via DecisionClassifier → DecisionSignal(is_decision, summary, confidence)
```

## Configuration

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `BRAVE_API_KEY` | Yes | Brave Search API key |
| `VECTOR_STORE_DIR` | No | Path for persistent index (default: `./vector_store_data`) |

## Environment

- Python 3.11+ (developed/tested on 3.14)
- Pure Python dependencies only (no Rust-native extensions)
