# Elia Research Agent Tool

Keyboard-centric internal Textual app for testing interview/research agent flow.

## Features

- Thread-based chats with local JSON state.
- Right research sidebar (edit research + chat context).
- Keyboard-first flow (`Ctrl+N` new thread, `Ctrl+J` send, `Ctrl+S` save local state).
- Fast send keys:
  - `F5` send as first ping
  - `F6` send as reply
- Quick controls for message types:
  - `Send first ping` (forces `first_message`)
  - `Send reply` (forces `user_reply`)
- Save / load research via Prompt Service contract:
  - `PUT /researches/{research_id}/prompt`
  - `GET /researches/{research_id}/prompt`
  - plus helper calls for `exists/latest-version/versions`
- Agent calls via Interview Agent contract:
  - `POST {AGENTS__INTERVIEW__URL|AGENT_URL}/{AGENT_ENDPOINT}`
  - `message_type`: `first_message` then `user_reply`.
- Pipeline rendering:
  - render only `batch`
  - ignore `trigger`
  - support `text` + quiet blocks for `voice/image/sticker`

## Environment

Copy `.env.example` and adjust values:

```bash
AGENTS__INTERVIEW__URL=http://localhost:3000
AGENT_URL=http://localhost:3000
AGENT_ENDPOINT=interview
PROMPT_SERVICE_URL=http://localhost:8001
APP_STATE_PATH=./data/state.json
```

Agent base URL priority:
1. `AGENTS__INTERVIEW__URL`
2. `AGENT_URL`
3. default `http://localhost:3000`

## Run (terminal)

```bash
uv run elia
# or
uv run elia run
```

## Run (browser)

```bash
uv run elia web --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000`.

## Docker (browser mode)

```bash
cp .env.example .env
docker compose up --build
```

Then open `http://localhost:8000`.

## Notes

- Prototype-only local storage (`APP_STATE_PATH`) and no external DB required.
- `research_id` must be filled before sending messages.
- `version` field in sidebar expects an integer (invalid values are ignored with warning).
- Thread title: `title` -> `research_id` -> `Untitled thread`.
- On `Save research`, missing/invalid required fields are auto-filled to valid defaults before sending.

## Smoke check (non-UI)

```bash
python scripts/smoke_flow_check.py
```

Expected output: `{"ok": true, "checks": ["state", "pipeline"]}`
