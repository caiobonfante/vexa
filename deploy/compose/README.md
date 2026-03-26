# Docker Compose Deployment

## Why
Full stack on your machine. All services, database, Redis — everything running locally. Best for development, testing, and self-hosted production without Kubernetes.

Before self-hosting, consider the hosted service at [vexa.ai](https://vexa.ai) — get an API key, no deployment needed. For simpler self-hosting, see [Vexa Lite](../lite/README.md).

## What

Runs all Vexa services via Docker Compose:
- API Gateway (port 8056)
- Admin API, Meeting API, Runtime API, Transcription Collector, MCP
- Dashboard
- TTS Service
- PostgreSQL + Redis + MinIO
- Bots spawn as Docker containers (needs Docker socket)

**You provide:** A transcription service — use [Vexa transcription](https://vexa.ai) (ready to go) or [self-host](../../services/transcription-service/) with GPU.

## How

### Quick start

```bash
# From repo root:
make all
```

That's it. Copies env-example → .env, builds images, starts services, runs migrations, tests connectivity.

**Before running**, edit `.env`:
1. Set `DASHBOARD_PATH` to your [vexa-dashboard](https://github.com/Vexa-ai/vexa-dashboard) checkout (absolute path)
2. Set `TRANSCRIPTION_SERVICE_URL` — get a key at [vexa.ai](https://vexa.ai) or [self-host](../../services/transcription-service/)

### Make targets

| Target | What it does |
|--------|-------------|
| `make all` | Full setup: env → build → up → migrate → test |
| `make env` | Create .env from template (if not exists) |
| `make build` | Build Docker images |
| `make up` | Start all services |
| `make down` | Stop all services |
| `make ps` | Show running containers |
| `make logs` | Tail all service logs |
| `make test` | Health check all services + show URLs |
| `make migrate` | Run database migrations |
| `make migrate-or-init` | Smart: init fresh DB or migrate existing |
| `make makemigrations M="msg"` | Create new migration |
| `make migration-status` | Show current migration version |

### Configuration

Edit `.env` at repo root. Created from [deploy/env/env-example](../env/env-example).

**Required:**
| Variable | Description |
|----------|-------------|
| DASHBOARD_PATH | Absolute path to [vexa-dashboard](https://github.com/Vexa-ai/vexa-dashboard) checkout |
| TRANSCRIPTION_SERVICE_URL | Your transcription endpoint. Get at [vexa.ai](https://vexa.ai) or [self-host](../../services/transcription-service/). |

Everything else has working defaults for local dev.

**Optional:**
| Variable | Default | Description |
|----------|---------|-------------|
| DASHBOARD_HOST_PORT | 3001 | Dashboard port |
| REMOTE_DB | false | Use external Postgres instead of local |
| LOCAL_TRANSCRIPTION | false | Run transcription-service locally (needs GPU) |
| BOT_IMAGE_NAME | vexa-bot:dev | Bot Docker image name |
| API_GATEWAY_HOST_PORT | 8056 | API Gateway port |
| ADMIN_API_HOST_PORT | 8057 | Admin API port |

Full env reference: [deploy/env/](../env/README.md)

### External database

```bash
# In .env:
REMOTE_DB=true
DB_HOST=your-postgres-host
DB_PORT=5432
DB_NAME=vexa
DB_USER=postgres
DB_PASSWORD=your-password
```

### Local GPU transcription

```bash
# In .env:
LOCAL_TRANSCRIPTION=true
# Then make up will also start services/transcription-service/
```

### Files

| File | Purpose |
|------|---------|
| docker-compose.yml | Main stack definition |
| docker-compose.local-db.yml | PostgreSQL overlay (used when REMOTE_DB≠true) |
| Makefile | All targets for compose workflow |
