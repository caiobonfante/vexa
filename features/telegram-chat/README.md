# Telegram Chat

> **Confidence: 40** — Core chat flow implemented and deployed (SSE streaming, user mapping, stop/interrupt). Not E2E tested against live agent-api. Missing: session commands, workspace commands, multi-message chunking for long responses.

## Why

Users need to interact with AI agents from mobile — not just the dashboard. Telegram is the most accessible interface. The chat feature lets users send messages, receive AI responses, manage workspaces, and control agent sessions — all from their phone. It's also the entry point for the scheduler: when a scheduled job completes, it sends results back through Telegram.

## What

- Telegram message -> agent-api `/api/chat` -> SSE response -> Telegram reply
- Session management: each Telegram user gets a persistent agent session via user mapping
- Commands: `/start` (info), `/reset` (reset session), `/new` (new session), `/workspace` (list files), `/sessions` (list sessions)
- Long responses chunked into multiple Telegram messages (4096 char limit)
- Markdown formatting converted to Telegram HTML
- Stop button for interrupting long responses
- Trigger API for scheduled messages (`POST /internal/trigger`)

### What exists (in `services/telegram-bot/bot.py`)

| Capability | Status | Evidence |
|------------|--------|----------|
| Receive Telegram messages | Done | `handle_message` handler |
| Map Telegram user -> agent user | Done | `USER_MAP`, `DEFAULT_USER_ID`, `tg_{id}` fallback |
| Forward to agent-api `/api/chat` | Done | SSE streaming in `_stream_response` |
| Progressive message editing | Done | `_safe_edit` with 1s interval |
| Tool use activity display | Done | `_TOOL_LABELS` + `_format_activity` |
| Markdown -> Telegram HTML | Done | `_to_html` (code blocks, bold, italic, links) |
| Stop button (interrupt) | Done | Inline keyboard + `_interrupt` |
| `/start` command | Done | Shows user ID |
| `/reset` command | Done | Calls `/api/chat/reset` |
| Trigger API | Done | FastAPI on port 8200 |
| Truncation (4096 limit) | Done | `_truncate` with indicator |

### What's missing

| Capability | Status | Notes |
|------------|--------|-------|
| `/new` command (new session) | Not implemented | Needs `POST /api/sessions` |
| `/workspace` command | Not implemented | Needs `GET /api/workspace/files` |
| `/sessions` command | Not implemented | Needs `GET /api/sessions` |
| Multi-message chunking | Not implemented | Currently truncates at 4096 chars |
| E2E test with live agent-api | Not tested | Core flow never validated end-to-end |
| Error handling for agent-api down | Partial | Catches exceptions but no retry/backoff |

## How

### Architecture

```
User on Telegram -> telegram-bot service -> agent-api -> runtime-api -> agent container
                                               |
                                         SSE chat response
                                               |
                                    telegram-bot sends reply
```

### Dependencies

- **agent-api** (`packages/agent-api`) — chat + sessions + workspace endpoints
- **telegram-bot** (`services/telegram-bot`) — existing service, this feature extends it
- **Runtime API** — container orchestration (agent-api depends on this)
- **Redis** — session state (agent-api depends on this)

### Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `TELEGRAM_BOT_TOKEN` | (required) | Telegram Bot API token |
| `CHAT_API_URL` | `http://agent-api:8100` | Agent API base URL |
| `BOT_API_TOKEN` | — | API key for agent-api auth |
| `CHAT_DEFAULT_USER_ID` | — | Default Vexa user ID (all chats map to this user) |
| `CHAT_USER_MAP` | `{}` | JSON map of `{"telegram_chat_id": "vexa_user_id"}` |
| `TELEGRAM_BOT_PORT` | `8200` | Trigger API port |

### Verify

1. Start agent-api + runtime-api + Redis
2. Set `TELEGRAM_BOT_TOKEN` and `CHAT_API_URL`
3. Run `python bot.py`
4. Send a message to the bot on Telegram
5. Verify SSE stream renders as progressive message edits
6. Press stop button — verify interruption works
7. `/reset` — verify session resets

## Implementation Plan

### Phase 1: Validate existing flow (E2E test)
1. Deploy telegram-bot + agent-api locally
2. Send a message, confirm response streams back
3. Document any issues in `tests/findings.md`

### Phase 2: Add session commands
1. `/new` — call `POST {AGENT_API_URL}/api/sessions` to create new session, update state
2. `/sessions` — call `GET {AGENT_API_URL}/api/sessions?user_id={user_id}`, format as list
3. Register commands with `set_my_commands`

### Phase 3: Add workspace command
1. `/workspace` — call `GET {AGENT_API_URL}/api/workspace/files?user_id={user_id}`
2. Format file list with sizes, show as code block

### Phase 4: Multi-message chunking
1. Split responses >4096 chars at paragraph boundaries
2. Send as sequence of messages instead of truncating
3. Keep stop button on last message only

### Phase 5: Resilience
1. Retry with backoff when agent-api is unreachable
2. Friendly "service unavailable" message after retries exhausted
3. Health check: `/status` command shows agent-api connectivity
