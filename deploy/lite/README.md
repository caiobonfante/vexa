# Vexa Lite Deployment

Single Docker container with the full Vexa stack. Needs external Postgres and a transcription service.

## Quick Start

```bash
# Build from repo root
docker build -f deploy/lite/Dockerfile.lite -t vexa-lite .

# Run (--shm-size=2g required for Chrome/Playwright browser sessions)
docker run -d \
  --name vexa \
  --shm-size=2g \
  -p 8056:8056 -p 3000:3000 \
  -e DATABASE_URL="postgresql://user:pass@host:5432/vexa" \
  -e ADMIN_API_TOKEN="your-secret-admin-token" \
  -e TRANSCRIBER_URL="http://host:8083/v1/audio/transcriptions" \
  -e TRANSCRIBER_API_KEY="your-api-key" \
  vexa-lite
```

### Storage

**Default (local):** Recordings stored at `/var/lib/vexa/recordings` inside the container. Mount a volume for persistence. Browser userdata lives in-memory only (lost on restart).

**With MinIO/S3:** Set `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` to enable S3-backed recordings and browser userdata persistence (login state survives restarts).

## Services

| Service | Port | Description |
|---------|------|-------------|
| API Gateway | 8056 | Main entry point — routes to all services |
| Admin API | 8057 | User/token management (internal) |
| Meeting API | 8080 | Bot orchestration + transcription pipeline (internal) |
| Runtime API | 8090 | Container lifecycle — process backend (internal) |
| Agent API | 8100 | AI agent chat runtime (internal) |
| Dashboard | 3000 | Next.js web UI (external) |
| MCP | 18888 | Model Context Protocol (internal) |
| TTS | 8059 | Text-to-speech (internal) |
| Redis | 6379 | Internal data store |
| Xvfb | :99 | Virtual display for browsers |

External: API Gateway (8056) and Dashboard (3000). Everything else is internal.

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                      Lite Container                            │
│                                                                │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌─────────────────┐ │
│  │ Dashboard │ │API Gatew.│ │ Admin API │ │   MCP Service   │ │
│  │  :3000   │ │  :8056   │ │   :8057   │ │     :18888      │ │
│  └──────────┘ └────┬─────┘ └───────────┘ └─────────────────┘ │
│                     │                                          │
│         ┌───────────┼───────────┬──────────────┐              │
│         ▼           ▼           ▼              ▼              │
│  ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │Meeting API│ │Runtime AP│ │Agent API │ │TTS Serv. │       │
│  │   :8080   │ │  :8090   │ │  :8100   │ │  :8059   │       │
│  └─────┬─────┘ └────┬─────┘ └──────────┘ └──────────┘       │
│        │             │                                        │
│        │      spawns processes                                │
│        │             ▼                                        │
│  ┌─────────────────────────────────────────────────────┐     │
│  │         Bot Processes (Node.js/Playwright)           │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                                │
│  ┌──────────┐  ┌────────────────┐  ┌──────────────────┐      │
│  │  Redis   │  │     Xvfb       │  │   PulseAudio     │      │
│  │  :6379   │  │     :99        │  │                   │      │
│  └──────────┘  └────────────────┘  └──────────────────┘      │
└────────────────────────────────────────────────────────────────┘
              │                    │
              ▼                    ▼
       ┌──────────────┐     ┌──────────┐
       │ Transcription │     │ Postgres │
       │   Service     │     │(external)│
       └──────────────┘     └──────────┘
```

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection URL |
| `ADMIN_API_TOKEN` | Secret token for admin operations |

### Transcription

| Variable | Description |
|----------|-------------|
| `TRANSCRIBER_URL` | Transcription service endpoint |
| `TRANSCRIBER_API_KEY` | API key for transcription |
| `SKIP_TRANSCRIPTION_CHECK` | Skip startup connectivity check (`true`/`false`) |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_HOST` | `localhost` | External Redis host (use localhost for internal) |
| `REDIS_PORT` | `6379` | Redis port |
| `LOG_LEVEL` | `info` | Logging level |
| `STORAGE_BACKEND` | `local` | Recording storage: `local`, `minio`, `s3` |
| `LOCAL_STORAGE_DIR` | `/var/lib/vexa/recordings` | Local recording directory |
| `OPENAI_API_KEY` | (empty) | For TTS service |

## Management

```bash
# Service status
docker exec vexa supervisorctl status

# Restart a service
docker exec vexa supervisorctl restart vexa-core:meeting-api

# View logs
docker logs -f vexa
```

## Testing

```bash
# Create user
curl -X POST "http://localhost:8056/admin/users" \
  -H "X-Admin-API-Key: your-admin-token" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "name": "Test User"}'

# Generate API token
curl -X POST "http://localhost:8056/admin/users/1/tokens" \
  -H "X-Admin-API-Key: your-admin-token"

# Start a bot
curl -X POST "http://localhost:8056/bots" \
  -H "X-API-Key: vx_abc123..." \
  -H "Content-Type: application/json" \
  -d '{"platform": "google_meet", "native_meeting_id": "abc-defg-hij", "bot_name": "Vexa Bot"}'
```

## Limitations

- 3-5 concurrent bots (shared CPU/RAM, process isolation)
- No GPU transcription (uses remote service)
- Redis data ephemeral unless volumes mounted
