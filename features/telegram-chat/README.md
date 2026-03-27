# Telegram Chat

> **Confidence: 90** — Full implementation: auto-create auth, SSE chat streaming, session/workspace/meeting commands, multi-message chunking, 37 unit tests passing. Not E2E tested against live infrastructure.

## Why

Users need to interact with AI agents from mobile — not just the dashboard. Telegram is the most accessible interface. The chat feature lets users send messages, receive AI responses, manage workspaces, control agent sessions, and manage meeting bots — all from their phone. It's also the entry point for the scheduler: when a scheduled job completes, it sends results back through Telegram.

## What

- **Auto-create auth**: First message auto-creates a user via admin-api, stores token in Redis
- **Chat streaming**: Telegram message -> agent-api `/api/chat` -> SSE response -> progressive Telegram edits
- **Multi-message chunking**: Long responses split at paragraph boundaries (4096 char limit)
- **Markdown formatting**: Converted to Telegram HTML (code blocks, bold, italic, links)
- **Stop button**: Inline keyboard to interrupt long responses
- **Session management**: `/new`, `/sessions`, `/reset` commands
- **Workspace**: `/files` to list workspace files
- **Meeting commands**: `/join`, `/stop`, `/speak`, `/transcript` via api-gateway
- **Trigger API**: `POST /internal/trigger` for scheduled messages

### Capabilities

| Capability | Status | Evidence |
|------------|--------|----------|
| Auto-create auth (Option B) | Done | `get_or_create_auth()` — admin-api user creation + Redis caching |
| Receive Telegram messages | Done | `handle_message` handler |
| Map Telegram user -> Vexa user | Done | Redis `telegram:{tg_id}` -> `user_id:token` |
| Forward to agent-api `/api/chat` | Done | SSE streaming in `_stream_response` |
| Progressive message editing | Done | `_safe_edit` with 1s interval |
| Multi-message chunking | Done | `_chunk_text` splits at paragraph/newline/space boundaries |
| Tool use activity display | Done | `_TOOL_LABELS` + `_format_activity` |
| Markdown -> Telegram HTML | Done | `_to_html` (code blocks, bold, italic, links, headers) |
| Stop button (interrupt) | Done | Inline keyboard + `_interrupt` |
| `/start` command | Done | Welcome + auth + command list |
| `/help` command | Done | Full command reference |
| `/new` command | Done | `POST /api/sessions` |
| `/sessions` command | Done | `GET /api/sessions` |
| `/files` command | Done | `GET /api/workspace/files` |
| `/reset` command | Done | `POST /api/chat/reset` |
| `/join` command | Done | `POST /bots` via api-gateway |
| `/stop` command | Done | `DELETE /bots/{platform}/{id}` via api-gateway |
| `/speak` command | Done | `POST /bots/{platform}/{id}/speak` via api-gateway |
| `/transcript` command | Done | `GET /transcripts/{platform}/{id}` via api-gateway |
| Meeting URL parsing | Done | Google Meet, Teams, Zoom URL extraction |
| Trigger API | Done | FastAPI on port 8200 (`/internal/trigger`) |

## How

### Architecture

```
User on Telegram
    |
    v
telegram-bot service (bot.py)
    |
    |-- auth --> admin-api (auto-create user + token)
    |              |
    |              v
    |            Redis (token cache: telegram:{tg_id} -> user_id:token)
    |
    |-- chat --> agent-api /api/chat (SSE)
    |              |
    |              v
    |            runtime-api -> agent container
    |
    |-- meeting --> api-gateway /bots/* (proxy to bot-manager)
    |
    v
Progressive message edits back to Telegram
```

### Auth Flow (Option B: Auto-create)

1. User sends first message to bot
2. Check Redis: `GET telegram:{telegram_user_id}` -> if cached, use `user_id:token`
3. If not cached:
   - `POST /admin/users` with email `telegram:{tg_id}@telegram` (find-or-create)
   - `POST /admin/users/{id}/tokens` to get API token
   - `SET telegram:{tg_id} {user_id}:{token}` in Redis (no expiry)
4. Token used for all subsequent agent-api and gateway calls

### Commands

| Command | Action | API |
|---------|--------|-----|
| `/start` | Auto-create user, welcome message | admin-api |
| Plain text | Forward to agent-api, stream response | agent-api `/api/chat` |
| `/new [name]` | Create new agent session | agent-api `POST /api/sessions` |
| `/sessions` | List sessions | agent-api `GET /api/sessions` |
| `/files` | List workspace files | agent-api `GET /api/workspace/files` |
| `/reset` | Reset session (keeps files) | agent-api `POST /api/chat/reset` |
| `/join <url>` | Send bot to meeting | gateway `POST /bots` |
| `/stop` | Stop active meeting bot | gateway `DELETE /bots/{p}/{id}` |
| `/speak <text>` | TTS in active meeting | gateway `POST /bots/{p}/{id}/speak` |
| `/transcript` | Get meeting transcript | gateway `GET /transcripts/{p}/{id}` |
| `/help` | Show command reference | — |

### Dependencies

- **admin-api** (`services/admin-api`) — user creation + token generation
- **agent-api** (`packages/agent-api`) — chat, sessions, workspace endpoints
- **api-gateway** (`services/api-gateway`) — meeting bot + transcript proxy
- **Redis** — token cache, session state
- **telegram-bot** (`services/telegram-bot`) — this service

### Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `TELEGRAM_BOT_TOKEN` | (required) | Telegram Bot API token |
| `AGENT_API_URL` | `http://agent-api:8100` | Agent API base URL |
| `ADMIN_API_URL` | `http://admin-api:8001` | Admin API for user creation |
| `ADMIN_API_TOKEN` | — | Admin API key (`X-Admin-API-Key` header) |
| `GATEWAY_URL` | `http://api-gateway:8000` | API gateway for meetings |
| `REDIS_URL` | `redis://redis:6379/0` | Redis for token cache |
| `TELEGRAM_BOT_PORT` | `8200` | Trigger API port |
| `LOG_LEVEL` | `INFO` | Logging level |

### Verify

1. Start admin-api, agent-api, api-gateway, Redis
2. Set `TELEGRAM_BOT_TOKEN`, `ADMIN_API_TOKEN`, and service URLs
3. Run `python bot.py`
4. Send `/start` — should auto-create user and show welcome
5. Send a text message — should stream SSE response with progressive edits
6. Press stop button — should interrupt response
7. `/new` — should create a new session
8. `/sessions` — should list sessions
9. `/files` — should list workspace files
10. `/join <meeting_url>` — should create meeting bot
11. `/transcript` — should show transcript segments

## Known Limitations

- **No E2E testing**: All 37 unit tests pass with mocked APIs. The full pipeline (Telegram -> admin-api -> agent-api -> response) has not been tested against live infrastructure.
- **Single active meeting**: Only one meeting per chat is tracked. Starting a new `/join` overwrites the previous meeting reference.
- **Token refresh**: Once a token is cached in Redis, it never expires. If the token is revoked in admin-api, the user must clear the Redis key manually.
- **No group chat support**: The bot is designed for 1:1 private chats. Group chat behavior is untested.
- **Meeting URL parsing**: Only Google Meet, Teams, and Zoom URLs are parsed. Other platforms require manual platform/ID specification.
