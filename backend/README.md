# Synapse Backend — Slack Bolt Application

Slack-facing service that wires the Synapse AI engine into a workspace via
Socket Mode. Handles events, builds Block Kit views, and extends the AI with
live data sources.

---

## Setup

```bash
cd backend
pip install -e "../ai-ml"       # editable link to the AI engine
pip install -e ".[dev]"
cp .env.example .env            # fill in all tokens and keys
pytest                          # 29 passed, 2 skipped (live)
python -m synapse_backend.app   # start the bot
```

## Slack App Configuration

Create an app at [api.slack.com/apps](https://api.slack.com/apps) and configure:

| Variable | Where to find it |
|---|---|
| `SLACK_BOT_TOKEN` | **OAuth & Permissions** → *Bot User OAuth Token* (after *Install to Workspace*). Starts with `xoxb-`. |
| `SLACK_APP_TOKEN` | **Basic Information** → *App-Level Tokens* → create a token with `connections:write` scope. Starts with `xapp-`. |
| `SLACK_SIGNING_SECRET` | **Basic Information** → *App Credentials* → *Signing Secret*. |
| `SLACK_USER_TOKEN` | **OAuth & Permissions** → *User OAuth Token* (requires `search:read.public`, `search:read.im` scopes). Starts with `xoxp-`. |
| `SLACK_DECISIONS_CHANNEL_ID` | Right-click channel → **Copy link** → extract `C...` ID. |
| `GITHUB_TOKEN` | GitHub Settings → **Developer settings** → **Personal access tokens** → Fine-grained PAT with `Contents: read`. |
| `GITHUB_REPO` | `owner/repo` string (e.g. `opeblow/synapse`). |

### Required bot scopes

- **Socket Mode** enabled.
- **Bot Token Scopes**: `chat:write`, `app_mentions:read`, `im:history`, `im:write`, `channels:history`
- **User Token Scopes** (for RTS): `search:read.public`, `search:read.im`
- **Subscribe to bot events**: `app_mention`, `message.im`, `app_home_opened`

No public URL or ngrok needed — Socket Mode connects over an outbound WebSocket.

## Project structure

```
src/synapse_backend/
├── config.py            # Typed Settings (pydantic-settings)
├── app.py               # Bolt app entry point
└── services/
    ├── github_mcp_client.py  # GitHub REST search wrapper
    └── rts_client.py         # Slack Real-Time Search API wrapper
tests/
├── conftest.py          # Placeholder env vars for test isolation
├── test_config.py       # 8 tests: defaults, overrides, validation
├── test_github_mcp_client.py  # 8 tests (1 live)
├── test_rts_client.py         # 11 tests (1 live)
└── test_smoke.py        # 3 tests: confirms ai-ml import works
```

## Running tests

```bash
pytest                        # 29 unit tests
RUN_LIVE_TESTS=1 pytest       # + 2 live API tests (requires .env)
```

## Development

```bash
black src/ tests/
ruff check src/ tests/
```

## Deployment (Render)

Two separate **Web Services** (standard tier, not Background Worker — both
are HTTP-aware and pass Render's health check).

### Root Directory

For both services, set Render's **Root Directory** to the repository root
(not `backend/`), so the monorepo's sibling `ai-ml` package can be resolved
during the build:

```
Root Directory:  (leave as repo root /  `./`)
```

### Build Command (shared)

```bash
pip install -e ai-ml && pip install -e backend
```

Editable installs (`-e`) are fine here because Render builds from a single
checkout and runs the same venv at runtime.

### Start Commands

| Service | Start Command |
|---|---|
| **Bot** (Socket Mode + health) | `python -m synapse_backend.app` |
| **API** (FastAPI) | `python -m synapse_backend.api` |

Both processes read `$PORT` from Render's environment. The bot runs its
health HTTP server on that port; the API passes it to uvicorn.

### Health Checks

Both services expose `GET /health` → `{"status": "ok"}`. Render will probe
this automatically once the start command binds the port.

### Required Environment Variables

#### Shared (set on **both** services)

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | OpenAI API key for embeddings and chat |
| `BRAVE_API_KEY` | Yes | Brave Search API key for web fallback |
| `GITHUB_TOKEN` | No | GitHub PAT for code search |
| `GITHUB_REPO` | No | `owner/repo` (e.g. `opeblow/synapse`) |
| `SLACK_USER_TOKEN` | No | Slack user token (`xoxp-...`) for RTS search |
| `LOG_LEVEL` | No | `DEBUG`, `INFO` (default), `WARNING`, etc. |

#### Bot service only

| Variable | Required | Description |
|---|---|---|
| `SLACK_BOT_TOKEN` | Yes | Bot User OAuth token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | Yes | App-Level token for Socket Mode (`xapp-...`) |
| `SLACK_SIGNING_SECRET` | Yes | Signing secret from Slack app credentials |
| `SLACK_DECISIONS_CHANNEL_ID` | No | Channel ID for Decision Cards |

#### API service only

*(No unique env vars — it uses the shared set above.)*

### Vector store seeding

On first boot, if the local vector store is empty, both processes
automatically seed it from `ai-ml/tests/fixtures/sample_docs.json`. No
manual `seed` command or committed binary data needed. The check is
lightweight (runs once at startup, skipped if docs already exist).

### Notes for the frontend teammate

Block Kit views live under `views/` and are pure functions: typed data in,
Block Kit dict out, no business logic. Replace the internals without changing
the function signatures.
