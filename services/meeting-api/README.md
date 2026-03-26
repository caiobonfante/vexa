# Meeting API

Meeting bot management service — join/stop bots, voice agent, recordings, webhooks, and callbacks from Runtime API.

## Port

- **8080** (default)

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `REDIS_URL` | yes | — | Redis connection URL |
| `DATABASE_URL` | yes | — | PostgreSQL async connection string |
| `RUNTIME_API_URL` | no | `http://runtime-api:8000` | Runtime API base URL |
| `MEETING_API_URL` | no | `http://meeting-api:8080` | Self URL for bot callbacks |
| `BOT_IMAGE_NAME` | no | `vexa-bot:latest` | Bot container image |
| `CORS_ORIGINS` | no | `http://localhost:3000,...` | Comma-separated CORS origins |
| `ADMIN_TOKEN` | yes | — | Secret for minting meeting JWTs |
| `TRANSCRIPTION_COLLECTOR_URL` | no | `http://transcription-collector:8000` | Transcription collector |

## Dependencies

- **Runtime API** — container lifecycle (create/stop)
- **PostgreSQL** — meeting state, recordings
- **Redis** — pub/sub, bot commands, chat messages

## API Endpoints

### Meeting CRUD
- `POST /bots` — create meeting bot
- `GET /bots/status` — list running bots (`running_bots` array)
- `DELETE /bots/{platform}/{id}` — stop bot
- `PUT /bots/{platform}/{meeting_id}/config` — update config

### Voice Agent
- `POST /bots/{platform}/{meeting_id}/speak` — TTS
- `POST /bots/{platform}/{meeting_id}/chat` — chat message
- `POST /bots/{platform}/{meeting_id}/screen` — screen content

### Recordings
- `GET /bots/{platform}/{meeting_id}/recordings` — list recordings

### Internal Callbacks
- `POST /bots/internal/callback/exited` — bot exit
- `POST /bots/internal/callback/started` — bot startup
- `POST /bots/internal/callback/joining` — bot joining
- `POST /bots/internal/callback/awaiting_admission`
- `POST /bots/internal/callback/status_change`

### Health
- `GET /health` → `{"status": "ok"}`
