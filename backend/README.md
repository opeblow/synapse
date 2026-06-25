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

## Notes for the frontend teammate

Block Kit views live under `views/` and are pure functions: typed data in,
Block Kit dict out, no business logic. Replace the internals without changing
the function signatures.
