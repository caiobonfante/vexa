# Runtime API

Central authority for container lifecycle management. Creates, tracks, and manages Docker containers across all profiles (agent, browser, meeting). Does not handle application logic like workspaces or meetings — those are concerns of the Agent API and Meeting API respectively.

## Key Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/containers` | Token | Create and start a container |
| `GET` | `/containers` | Token | List containers (filter by `user_id`, `profile`) |
| `GET` | `/containers/{name}` | None | Get container details |
| `DELETE` | `/containers/{name}` | Token | Stop and remove a container |
| `POST` | `/containers/{name}/touch` | None | Update activity timestamp (keeps container alive) |
| `GET` | `/containers/{name}/cdp` | None | Get CDP URL for browser containers |
| `GET` | `/health` | None | Health check with container counts |

## Container Profiles

- **agent** — One per user (deterministic name `vexa-agent-{user_id}`). Runs Claude CLI with workspace mount and credentials.
- **browser** — Headless browser sessions with CDP access. Unique name per instance. Supports S3-backed profile persistence.
- **meeting** — Meeting bot containers. Unique name per instance. No idle timeout.

## Architecture

- **State**: Container metadata stored in Redis, reconciled with Docker on startup.
- **Idle management**: Background loop stops containers that exceed their profile's idle timeout.
- **Auth**: Token-based authentication via the shared database.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCKER_HOST` | `unix:///var/run/docker.sock` | Docker daemon socket |
| `DOCKER_NETWORK` | `vexa-agentic_vexa_agentic` | Docker network for containers |
| `REDIS_URL` | `redis://redis:6379` | Redis connection URL |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:3001` | Allowed CORS origins |
| `AGENT_IMAGE` | `vexa-agent:dev` | Docker image for agent containers |
| `BROWSER_IMAGE` | `vexa-bot:dev` | Docker image for browser containers |
| `MEETING_IMAGE` | `vexa-bot:dev` | Docker image for meeting containers |
| `AGENT_IDLE_TIMEOUT` | `900` | Agent idle timeout (seconds) |
| `BROWSER_IDLE_TIMEOUT` | `600` | Browser idle timeout (seconds) |
| `IDLE_CHECK_INTERVAL` | `30` | Seconds between idle checks |
| `MINIO_ENDPOINT` | `minio:9000` | MinIO endpoint |
| `MINIO_ACCESS_KEY` | `vexa-access-key` | MinIO access key |
| `MINIO_SECRET_KEY` | `vexa-secret-key` | MinIO secret key |
| `MINIO_BUCKET` | `vexa-recordings` | MinIO bucket |
| `CLAUDE_CREDENTIALS_PATH` | — | Host path to Claude credentials |
| `CLAUDE_JSON_PATH` | — | Host path to claude.json |
| `BOT_API_TOKEN` | — | Token passed to agent containers for meeting-api calls |
| `LOG_LEVEL` | `INFO` | Log level |

## Running Locally

```bash
cd services/runtime-api
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8090 --reload
```

Requires Redis, PostgreSQL, and Docker daemon access.
