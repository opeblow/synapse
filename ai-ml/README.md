# Synapse AI — AI/ML Engine

Self-contained RAG engine powering the Synapse Slack bot. Provides retrieval-augmented
Q&A, decision detection, and web search fallback — zero Slack coupling.

---

## Setup

```bash
cd ai-ml
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env       # fill in your API keys
pytest                     # 48 tests (3 skipped: live integration)
```

## Configuration

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `BRAVE_API_KEY` | Yes | Brave Search API key |
| `VECTOR_STORE_DIR` | No | Persist path (default: `./vector_store_data`) |

## CLI

```bash
# Seed the vector store with sample documents
python -m synapse_ai.cli seed

# Ask a question (vector store + optional web fallback)
python -m synapse_ai.cli ask "What is the team's deployment policy?"
python -m synapse_ai.cli ask "How do we handle on-call incidents?"
python -m synapse_ai.cli ask "What's the capital of France?"    # falls back to web
```

## Architecture

```
                  Orchestrator
                 /            \
          Retriever       DecisionClassifier
         /         \              |
  VectorStore   BraveSearch    OpenAI
  (NumPy)        (web)        (LLM)
```

- **Vector store**: pure NumPy, no Rust deps. Persisted as `index.json` + `vectors.npy`.
- **Routing**: confidence ≥0.70 → vector only; ≥0.35 → vector + web; else → web only.
- **Decision detection**: analyses transcripts via LLM JSON extraction.

## Project structure

```
src/synapse_ai/
├── clients/                # OpenAI & Brave Search wrappers
├── vectorstore/store.py    # Document, ScoredChunk, VectorStore
├── retrieval/retriever.py  # Retriever (embed + query)
├── agent/
│   ├── orchestrator.py     # Orchestrator, AnswerResult, Source
│   └── decision_classifier.py  # DecisionClassifier, DecisionSignal
├── config.py               # pydantic-settings
└── cli.py                  # seed / ask commands
tests/
├── conftest.py
├── fixtures/sample_docs.json
├── test_*.py               # one per module
└── smoke tests for live integration (gated by RUN_LIVE_TESTS=1)
```

## Running tests

```bash
pytest                        # 48 fast unit tests
RUN_LIVE_TESTS=1 pytest       # includes 3 live API calls
```

## Notes

- Python 3.11+ (tested on 3.14). Pure Python — no Rust-native extensions.
- `.env` is auto-discovered by walking up from CWD; run CLI from `ai-ml/`.
