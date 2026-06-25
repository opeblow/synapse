<div align="center">

![Synapse Logo](./ai-ml/docs/logo.svg)

</div>

<div align="center">

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![License](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000?style=for-the-badge)](https://github.com/astral-sh/ruff)
[![Checked with black](https://img.shields.io/badge/code%20style-black-000000?style=for-the-badge)](https://github.com/psf/black)

<br>

**Cited, cross-source institutional memory for your Slack workspace.**

</div>

---

## Problem

Slack teams make hundreds of decisions every week — deployment dates, tech
choices, process changes — but they evaporate into endless scroll. Repeating
the same question to different people, or searching across channels manually,
wastes time and breeds inconsistency. There is no cross-referenced,
persistent memory of *what* was decided, *why*, and *where* the source lives.

## Solution

Synapse is a Slack-native AI agent that lives in your workspace. When a
decision is detected (or a question is asked), it retrieves the most
relevant context from **four parallel sources** — your local knowledge base,
your own Slack conversation history, the open web, and your GitHub
repository — and synthesises a cited, conversational answer. Every source
is attributed so the reader can verify the original.

---

## What's built (CONFIRMED WORKING)

| Layer | Technology | Status |
|---|---|---|
| **Slack integration** | Slack Bolt (Socket Mode) — no public URL | Connected, live-tested |
| **RAG pipeline** | OpenAI embeddings + NumPy vector store | Answers from seeded docs with citations |
| **Web fallback** | Brave Search API | Works when local docs don't match |
| **GitHub code search** | GitHub REST API (MCP-style wrapper) | Supplementary source; fail-safe if repo isn't indexed |
| **Slack RTS search** | `assistant.search.context` API (user token) | Searches workspace conversation history as fallback source |
| **Decision detection** | LLM-based classifier + transcript analysis | Auto-posts a "Decision Detected" card to `#decisions` |
| **Tests** | pytest, all network calls mocked | **Backend: 29 passed / 2 skipped** (live tests gated by `RUN_LIVE_TESTS=1`) |
| | | **AI/ML: 54 passed / 3 skipped** (live tests gated by `RUN_LIVE_TESTS=1`) |

---

## Architecture

```
  Slack (Socket Mode)
       │ app_mention / message.im
       ▼
  ┌──────────────────────────────┐
  │   Slack Bolt App             │
  │   (synapse_backend/app.py)   │
  └──────────┬───────────────────┘
             │ answer()
             ▼
  ┌──────────────────────────────┐
  │       Orchestrator           │
  │   (synapse_ai/orchestrator)  │
  │                              │
  │  1. Retriever (vector store) │
  │     │ score ≥ 0.70 → answer  │
  │     │ score < 0.70 → fallback│
  │     ▼                        │
  │  2. RTS (Slack history)──────┤  ◄── NEW — runs first in fallback
  │     ▼                        │
  │  3. Brave (web search)───────┤
  │     ▼                        │
  │  4. GitHub (code search)─────┤
  │     ▼                        │
  │  5. OpenAI LLM — synthesise  │
  │     answer with [1][2] cites │
  └──────────────────────────────┘
         │            │
         ▼            ▼
  Decision        Answer
  Classifier      + Sources
  (LLM-based)     (to Slack)
```

**Routing logic:**
1. Retrieve chunks from the local vector store.
2. **Score ≥ 0.70** — answer with high confidence from vector store alone.
3. **Score ≥ 0.35** — also fetch RTS + Brave + GitHub; medium confidence.
4. **Score < 0.35** — fall back to RTS + Brave + GitHub only; low confidence.
5. All three fallback sources (RTS, Brave, GitHub) are resilient: if one
   fails or returns nothing, the others still contribute.
6. If *no* sources are found at all, Synapse replies "I don't know."

---

## Repository structure

```
synapse/
├── ai-ml/                            # Core AI/ML engine
│   ├── src/synapse_ai/
│   │   ├── agent/
│   │   │   ├── orchestrator.py       # Orchestrator, Source, AnswerResult
│   │   │   └── decision_classifier.py
│   │   ├── clients/
│   │   │   ├── openai_client.py
│   │   │   └── brave_search_client.py
│   │   ├── retrieval/retriever.py
│   │   ├── vectorstore/store.py
│   │   ├── config.py
│   │   └── cli.py
│   ├── tests/                        # 57 tests (54 pass, 3 live)
│   └── README.md
│
├── backend/                          # Slack-facing application
│   ├── src/synapse_backend/
│   │   ├── app.py                    # Bolt entry point, event handlers
│   │   ├── config.py                 # pydantic-settings
│   │   ├── services/
│   │   │   ├── github_mcp_client.py  # GitHub REST search wrapper
│   │   │   └── rts_client.py         # Slack RTS API wrapper
│   │   └── views/                    # Block Kit view builders
│   ├── tests/                        # 31 tests (29 pass, 2 live)
│   └── README.md
│
└── README.md                         # This file
```

---

## Quick start

```bash
# 1. AI/ML module — seed the vector store and test the engine
cd ai-ml
pip install -e ".[dev]"
cp .env.example .env       # fill in OPENAI_API_KEY and BRAVE_API_KEY
pytest                     # 54 passed, 3 skipped (live)
python -m synapse_ai.cli seed
python -m synapse_ai.cli ask "What is our deployment policy?"

# 2. Backend — run the Slack bot
cd ../backend
pip install -e "../ai-ml"
pip install -e ".[dev]"
cp .env.example .env       # fill in Slack tokens + API keys
pytest                     # 29 passed, 2 skipped (live)
python -m synapse_backend.app
```

---

## Environment variables

All secrets live in `backend/.env` (loaded at startup). The `ai-ml/` module
reads from `os.environ`, picking up whatever `backend/app.py` loaded.

| Variable | Required | Where to get it |
|---|---|---|
| `SLACK_BOT_TOKEN` | Yes | Slack App → **OAuth & Permissions** (`xoxb-...`) |
| `SLACK_APP_TOKEN` | Yes | Slack App → **Basic Information** → App-Level Tokens (`xapp-...`) |
| `SLACK_SIGNING_SECRET` | Yes | Slack App → **Basic Information** → Signing Secret |
| `SLACK_USER_TOKEN` | Yes | Slack App → **OAuth & Permissions** → User OAuth Token (`xoxp-...`) |
| `OPENAI_API_KEY` | Yes | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `BRAVE_API_KEY` | Yes | [api.search.brave.com](https://api.search.brave.com) |
| `SLACK_DECISIONS_CHANNEL_ID` | For decision cards | Channel ID (e.g. `C0123ABC456`) |
| `GITHUB_TOKEN` | For GitHub search | GitHub PAT with `repo` scope |
| `GITHUB_REPO` | For GitHub search | `owner/repo` string |
| `LOG_LEVEL` | No | `INFO` (default), `DEBUG`, etc. |

---

## Not yet built

These pieces are on the roadmap but not implemented:

- **App Home digest** — the native Slack "Home" tab showing a dashboard of
  recent decisions, a search bar, and trend charts. This was the third pillar
  of the original three-technology pitch (RAG + decision detection + App Home).
- **Block Kit frontend polish** — answer views are functional but minimal;
  richer interactive components (thread summaries, pagination, feedback
  buttons) are still pending.
- **Automatic channel watching** — currently Synapse only responds to
  `@mentions` and DMs. Proactive scanning of public channels for decisions
  is planned.
- **Auto-indexing** — the knowledge base is populated by `cli.py seed`;
  automatic indexing from connected sources is future work.

---

## Technology

- **Python 3.11+** (developed and tested on 3.14)
- **Slack Bolt** — Socket Mode (no public URL needed)
- **OpenAI** — embeddings (`text-embedding-3-small`) and chat completions (`gpt-4o-mini`)
- **Brave Search API** — web search fallback
- **Slack Real-Time Search API** — `assistant.search.context` with user token
- **GitHub REST API** — code search via `/search/code`
- **NumPy** — pure-Python vector store (no Rust-native extensions)
- **pydantic-settings** — typed environment configuration
- **httpx** — HTTP client with timeout + retry
- **pytest** — full test coverage with mocked network calls

---

## Hackathon context

- **Track:** [TODO]
- **Team:** [TODO]
- **Demo video:** [TODO]
- **Devpost:** [TODO]

---

## License

MIT
