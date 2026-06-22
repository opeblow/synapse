# Synapse Backend

Slack Bolt backend for Synapse — retrieval-augmented Q&A and decision detection
powered by the `synapse-ai` module.

---

## Slack App Setup

Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps) and
configure the following.

### Required environment variables

| Variable | Where to find it |
|---|---|
| `SLACK_BOT_TOKEN` | **OAuth & Permissions** → *Bot User OAuth Token* (available after *Install to Workspace*). Starts with `xoxb-`. |
| `SLACK_APP_TOKEN` | **Basic Information** → *App-Level Tokens* → generate a token with the `connections:write` scope. Starts with `xapp-`. |
| `SLACK_SIGNING_SECRET` | **Basic Information** → *App Credentials* → *Signing Secret*. |

### Socket Mode

This app runs in **Socket Mode** — no public URL or ngrok needed. Enable Socket
Mode in your app config under **Socket Mode** → *Enable Socket Mode*.

### Bot Token Scopes

Add these under **OAuth & Permissions** → *Scopes* → *Bot Token Scopes*:

- `chat:write` — post messages
- `app_mentions:read` — receive mentions
- `im:history` — read direct messages
- `im:write` — send direct messages
- `channels:history` — read public channel history

### Subscribed Events

Add these under **Event Subscriptions** → *Subscribe to bot events*:

- `app_mention` — bot is @-mentioned
- `message.im` — direct message received
- `app_home_opened` — user opens App Home tab

---

## Quick start

```bash
cd backend
pip install -e ../ai-ml
pip install -e ".[dev]"
cp .env.example .env   # fill in real tokens
pytest                  # 11 tests should pass
```

Run the bot:

```bash
python -m synapse_backend.app
```

---

## Project structure

```
backend/
├── src/synapse_backend/
│   ├── __init__.py
│   ├── config.py       # Typed Settings from environment
│   └── app.py          # Bolt app entry point (Socket Mode)
├── tests/
│   ├── __init__.py
│   ├── conftest.py     # Placeholder env vars for tests
│   ├── test_config.py
│   └── test_smoke.py   # Verifies synapse-ai is importable
├── pyproject.toml
├── .env.example
└── .gitignore
```

---

## Development

```bash
black src/ tests/
ruff check src/ tests/
```
