# Services Architecture

## Why

Vexa is a dozen services, not a monolith. Each service owns one concern (transcription, bot lifecycle, user management, agent chat) and communicates via REST and Redis. This map exists because no single service tells you how the whole system works — you need the wiring diagram to understand data flow, port assignments, and which service calls which.

## What

### System Diagram

```
                      ┌─────────────┐
                      │   Dashboard  │
                      │   (Next.js)  │
                      └──────┬───────┘
                             │
                      ┌──────▼───────┐
                      │ API Gateway  │
                      └──────┬───────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
   ┌──────▼─────┐    ┌──────▼──────┐    ┌──────▼─────┐
   │ Admin API  │    │ Meeting API │    │  Agent API  │
   │(users,     │    │(join, stop, │    │(chat, tts,  │
   │ tokens)    │    │ status, wh) │    │ workspace)  │
   └────────────┘    └──────┬──────┘    └──────┬──────┘
                            │                  │
                   ═════════╪══════════════════╪═══════
                    domain  │                  │
                    ────────┼──────────────────┘
                    infra   │
                            │
                   ┌────────▼────────┐
                   │  Runtime API    │  ← packages/runtime-api/
                   │                 │
                   │ • CRUD API      │
                   │ • YAML profiles │
                   │ • idle mgmt    │
                   │ • callbacks     │
                   │ • concurrency   │
                   └────────┬────────┘
                            │
                   ┌────────┼────────┐
                   │        │        │
             ┌─────▼──┐ ┌──▼───┐ ┌──▼──────┐
             │ Docker │ │ K8s  │ │ Process │
             │ socket │ │ pods │ │ child   │
             └───┬────┘ └──┬───┘ └────┬────┘
                 │         │          │
            ┌────▼───┐ ┌───▼──┐ ┌────▼─────┐
            │vexa-bot│ │agent │ │ browser  │
            │(meetng)│ │(CLI) │ │(Chromium)│
            └────┬───┘ └──────┘ └──────────┘
                 │
         ┌───────┴────────┐
         │  Redis streams  │
         ▼                 ▼
┌──────────────┐  ┌─────────────────┐
│  Meeting API │  │ Transcription   │
│  (collector  │  │   Service       │
│   built-in)  │  │ (Whisper API)   │
└──────────────┘  └─────────────────┘
```

## Publishable Packages

These live in `packages/` and are designed to be independently publishable with no Vexa-specific domain knowledge.

| Package | Description |
|---------|-------------|
| [runtime-api](../packages/runtime-api/) | Generic container lifecycle API — Docker, K8s, and process backends |
| [agent-api](../packages/agent-api/) | AI agent runtime — chat streaming, workspace sync, scheduling |
| [shared-models](../libs/shared-models/) | SQLAlchemy models, Pydantic schemas, DB migrations (deprecated, in `libs/`) |

## Services

### API Layer

| Service | Port | Description |
|---------|------|-------------|
| [api-gateway](api-gateway/) | 8000 | Entry point. Auth middleware, routing, CORS |
| [admin-api](admin-api/) | 8001 | User management, API tokens, meeting CRUD |
| [agent-api](agent-api/) | 8100 | Chat sessions, TTS, scheduling (in-process worker), workspaces |
| [runtime-api](../packages/runtime-api/) | 8090 | Container lifecycle API — Docker, K8s, process backends. Lives in `packages/`. |

### Domain Services

| Service | Description |
|---------|-------------|
| [meeting-api](meeting-api/) | Meeting domain — bot lifecycle, recordings, callbacks, webhooks |
| [vexa-bot](vexa-bot/) | Browser-based meeting bot (Zoom, Google Meet, MS Teams) |
| [vexa-agent](vexa-agent/) | Claude Code agent container |

### Transcription Pipeline

| Service | Port | Description |
|---------|------|-------------|
| [transcription-service](../packages/transcription-service/) | 8083 | Whisper API — speech-to-text (in `packages/`) |
| [transcription-collector](transcription-collector/) | 8002 | Consumes Redis streams, writes segments to DB |
| [transcript-rendering](transcript-rendering/) | — | TypeScript library for dedup, grouping, timestamps |

### Supporting Services

| Service | Port | Description |
|---------|------|-------------|
| [tts-service](../packages/tts-service/) | 8084 | Text-to-speech for voice agent participation (in `packages/`) |
| [mcp](mcp/) | 8010 | Model Context Protocol server for AI tool integration |
| [calendar-service](calendar-service/) | 8085 | Google Calendar sync, auto-join scheduling |
| [telegram-bot](telegram-bot/) | — | Telegram interface for mobile meeting management |
| [dashboard](dashboard/) | 3000 | Next.js web UI — meetings, admin, agent chat |

## Data Flow

### Meeting Transcription
1. **Meeting API** receives join request → **Runtime API** spawns **vexa-bot** container
2. **vexa-bot** joins meeting via browser, captures audio per speaker
3. Audio sent via HTTP to **Transcription Service** (Whisper) → text returned
4. Segments published to **Redis streams**
5. **Transcription Collector** consumes streams → writes to PostgreSQL
6. **Dashboard** reads transcripts from DB via **API Gateway**

### Agent Chat
1. **Agent API** receives chat request → **Runtime API** spawns **vexa-agent** container
2. **vexa-agent** runs Claude Code with workspace context
3. Responses streamed back via SSE through **Agent API** → **Dashboard**

### Scheduler

The scheduler is not a standalone service — it runs as an in-process worker inside **Agent API**. It uses Redis sorted sets to queue future HTTP calls (e.g., "join this meeting at 2pm").

**Flow:** Calendar Service syncs events → Agent API scheduler queues timed job → job fires → API Gateway → Meeting API spawns bot.

**Code:** `libs/shared-models/shared_models/scheduler.py` + `scheduler_worker.py`

## Infrastructure Dependencies

- **PostgreSQL** — persistent storage (meetings, transcripts, users, tokens)
- **Redis** — streams (transcription segments, speaker events), pub/sub (bot commands), sorted sets (scheduler)
- **S3/MinIO** — recording storage (audio, video)
