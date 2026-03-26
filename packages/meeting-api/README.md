# Meeting API

## Why

Every meeting platform (Google Meet, Teams, Zoom) has its own join flow, audio model, and lifecycle quirks. Something needs to own this complexity so the rest of the system doesn't have to care which platform a meeting is on. Meeting API is the domain boundary: it translates a single `POST /bots` request into platform-specific container orchestration, manages bot state through the full lifecycle (joining → active → completed), and exposes a uniform interface for voice agent controls, recordings, and status callbacks. Without it, every client would reimplement platform-specific bot management.

## What

Bot lifecycle management service. Handles meeting CRUD, voice agent controls (TTS, chat, screen sharing), recording management, and bot status callbacks from Runtime API.

**Port:** 8080 (default)

### Dependencies

- **Runtime API** — container lifecycle (create/stop)
- **PostgreSQL** — meeting state, recordings
- **Redis** — pub/sub, bot commands, chat messages

### API Endpoints

#### Meeting CRUD
- `POST /bots` — create meeting bot
- `GET /bots/status` — list running bots (`running_bots` array)
- `DELETE /bots/{platform}/{id}` — stop bot
- `PUT /bots/{platform}/{meeting_id}/config` — update config

#### Voice Agent
- `POST /bots/{platform}/{meeting_id}/speak` — TTS
- `POST /bots/{platform}/{meeting_id}/chat` — chat message
- `POST /bots/{platform}/{meeting_id}/screen` — screen content

#### Recordings
- `GET /bots/{platform}/{meeting_id}/recordings` — list recordings

#### Internal Callbacks
- `POST /bots/internal/callback/exited` — bot exit
- `POST /bots/internal/callback/started` — bot startup
- `POST /bots/internal/callback/joining` — bot joining
- `POST /bots/internal/callback/awaiting_admission`
- `POST /bots/internal/callback/status_change`

#### Health
- `GET /health` → `{"status": "ok"}`

## How

### Environment Variables

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

