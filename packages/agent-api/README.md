# Agent API

## Why

Running an LLM agent inside a container is the easy part. The hard parts are everything around it: routing user messages to the right container, resuming sessions after container restarts, syncing workspace files so work survives reboots, and scheduling future jobs without a separate cron service. Every AI product that wants stateful agents in containers solves these problems from scratch. Agent API packages the application layer — chat routing, sessions, workspace persistence, scheduling — so you wire it to [Runtime API](../runtime-api/) for container ops and get a complete agent backend.

## What

AI agent runtime framework. Route user messages to LLM agents running inside ephemeral containers, with session management, workspace persistence, and job scheduling.

## Features

- **Chat streaming** — SSE-based message routing to agents via container exec
- **Session management** — persistent sessions with Redis-backed state (7-day TTL)
- **Workspace sync** — S3-compatible workspace persistence across container restarts
- **Job scheduling** — Redis sorted set scheduler for deferred and recurring tasks
- **Container lifecycle** — delegates to [Runtime API](../runtime-api/) for container orchestration
- **One agent per user** — deterministic container naming with automatic reuse

## How

### Quickstart

### Docker Compose (recommended)

```bash
docker compose up -d
```

Requires Runtime API and Redis running alongside.

### From source

```bash
pip install -e .
uvicorn agent_api.main:app --host 0.0.0.0 --port 8100
```

### Send a chat message

```bash
# Stream a response from the agent (SSE)
curl -N -X POST http://localhost:8100/api/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "user_id": "user-1",
    "message": "What files are in the workspace?"
  }'
```

### List sessions

```bash
curl http://localhost:8100/api/sessions?user_id=user-1 \
  -H "X-API-Key: your-api-key"
```

### Schedule a job

```bash
curl -X POST http://localhost:8100/api/schedule \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "execute_at": "2025-01-15T14:00:00Z",
    "request": {
      "method": "POST",
      "url": "http://my-service:8080/tasks/run",
      "body": {"task": "daily-report"}
    }
  }'
```

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat` | Send message, receive SSE stream of agent responses |
| `DELETE` | `/api/chat` | Interrupt an in-progress chat turn |
| `POST` | `/api/chat/reset` | Reset the chat session (keeps workspace files) |
| `GET` | `/api/sessions` | List all sessions for a user |
| `POST` | `/api/sessions` | Create a new named session |
| `PUT` | `/api/sessions/{id}` | Rename a session |
| `DELETE` | `/api/sessions/{id}` | Delete a session |
| `GET` | `/api/workspace/files` | List files in a user's workspace |
| `GET` | `/api/workspace/file` | Get file content from workspace |
| `POST` | `/api/workspace/file` | Write a file to the workspace |
| `POST` | `/api/schedule` | Schedule a deferred HTTP request |
| `GET` | `/api/schedule` | List scheduled jobs |
| `DELETE` | `/api/schedule/{id}` | Cancel a scheduled job |
| `POST` | `/internal/workspace/save` | Sync workspace from container to S3 |
| `GET` | `/internal/workspace/status` | Check workspace and container status |
| `GET` | `/health` | Health check |

## Architecture

```
  User / Frontend
       │
       ▼
┌──────────────┐
│ Agent API │
│              │
│ • chat SSE   │     ┌──────────────┐
│ • sessions   │────▶│  Runtime API  │──▶ Docker / K8s / Process
│ • scheduler  │     └──────────────┘
│ • workspaces │
└──────┬───────┘
       │
  ┌────┴────┐
  ▼         ▼
Redis    S3/MinIO
(state)  (workspaces)
```

### How chat works

1. User sends message via `POST /api/chat`
2. Agent API ensures agent container is running (via Runtime API)
3. Executes LLM CLI inside container via `docker exec`
4. Streams response back as SSE events
5. Session state saved to Redis for continuity

### Scheduling

The scheduler uses Redis sorted sets to queue future HTTP requests. An in-process worker loop polls for due jobs and fires them.

```
Schedule job → Redis sorted set (score = execute_at timestamp)
                    │
Worker loop polls every 5s (configurable)
                    │
                    ▼
Fire HTTP request → target URL
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_RUNTIME_PORT` | `8100` | Server port |
| `REDIS_URL` | `redis://redis:6379` | Redis connection URL |
| `RUNTIME_API_URL` | `http://runtime-api:8090` | Runtime API for container lifecycle |
| `API_KEY` | — | API key for authentication (empty = open access) |
| `AGENT_IMAGE` | `agent:latest` | Docker image for agent containers |
| `AGENT_CLI` | `claude` | Agent CLI command inside containers |
| `AGENT_ALLOWED_TOOLS` | `Read,Write,Edit,Bash,Glob,Grep` | Tools the agent CLI can use |
| `DEFAULT_MODEL` | — | Default LLM model for the agent |
| `DOCKER_NETWORK` | — | Docker network to attach containers to |
| `CONTAINER_PREFIX` | `agent-` | Prefix for container names |
| `IDLE_TIMEOUT` | `300` | Seconds before idle containers are stopped |
| `STORAGE_BACKEND` | `local` | Storage backend: `local` or `s3` |
| `WORKSPACE_PATH` | `/workspace` | Workspace path inside containers |
| `S3_ENDPOINT` | — | S3-compatible endpoint for workspace persistence |
| `S3_ACCESS_KEY` | — | S3 access key |
| `S3_SECRET_KEY` | — | S3 secret key |
| `S3_BUCKET` | `workspaces` | S3 bucket for workspaces |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |
| `LOG_LEVEL` | `INFO` | Log level |
| `SCHEDULER_POLL_INTERVAL` | `5` | Seconds between scheduler polls |

## Use Cases

- **AI coding assistants** — isolated dev containers with workspace persistence
- **Customer support agents** — stateful conversation agents with tool access
- **Data analysis agents** — sandboxed environments for running analysis code
- **Workflow automation** — agents that execute multi-step tasks with scheduling

## Relationship to Runtime API

Agent API handles the **application layer** — chat routing, sessions, workspaces, scheduling. It delegates all **container operations** (create, stop, idle management) to [Runtime API](../runtime-api/).

```
Agent API = what the agent does
Runtime API   = where the agent runs
```

## Production Readiness

**Confidence: 38/100**

| Area | Score | Evidence | Gap |
|------|-------|----------|-----|
| Core chat streaming | 7/10 | SSE routing, session resumption, retry logic work | No tests for chat.py or main.py endpoints; no timeout on agent CLI exec |
| Session management | 8/10 | Redis-backed with 7-day TTL, CRUD endpoints complete | Hardcoded session path `/root/.claude/projects/-workspace/` is brittle |
| Workspace sync | 5/10 | S3 + local backends, path traversal protection | AWS CLI dependency undocumented; no tests for S3 ops or git_commit(); large files loaded into memory |
| Job scheduling | 0/10 | Config var `SCHEDULER_POLL_INTERVAL` exists | **Entirely missing.** No endpoints, no worker loop, no Redis sorted set. README documents it as a core feature but zero code exists |
| Authentication | 9/10 | `hmac.compare_digest()` timing-safe comparison, open-access dev mode | CORS defaults to `*`; empty API_KEY silently disables auth |
| Container lifecycle | 5/10 | Runtime API delegation, in-memory cache, interrupt support | No cache invalidation on container death; race condition between cache check and exec; `_touch()` assumes Runtime API support |
| Tests | 4/10 | 44 unit tests across auth, stream_parser, workspace, container_manager | **0% coverage on chat.py and main.py** — the two most critical files. No integration tests. Container exec operations untested |
| Docker | 4/10 | Builds, runs on port 8100 | No HEALTHCHECK; runs as root; no docker-compose at package level |
| Documentation | 6/10 | Comprehensive README with architecture diagram | Documents scheduler feature that doesn't exist; 5 env vars are unused (AGENT_IMAGE, DOCKER_NETWORK, CONTAINER_PREFIX, IDLE_TIMEOUT, SCHEDULER_POLL_INTERVAL) |
| Standalone readiness | 5/10 | Can start without Runtime API; sessions work Redis-only | Any chat request fails without Runtime API + Docker daemon + running container; no graceful error for missing deps |

### Known Limitations

1. **Scheduler is vaporware** — README, architecture diagram, env vars, and API table all document a scheduling feature. No implementation exists. Zero lines of scheduler code.
2. **Core paths untested** — `chat.py` (the main feature) and `main.py` (all HTTP endpoints) have 0% test coverage. The 44 existing tests cover supporting modules only.
3. **Hardcoded container assumptions** — session path (`/root/.claude/projects/-workspace/`), process pattern (`claude.*stream-json`), and agent CLI (`claude`) are baked in. Changing the agent image breaks chat.
4. **No standalone docker-compose** — requires separate Runtime API, Redis, and Docker daemon. No single-command local dev setup.
5. **S3 sync requires AWS CLI in container image** — undocumented dependency. If the agent image lacks `aws`, workspace persistence silently fails.
6. **No request tracing** — no correlation IDs in logs. Debugging cross-service issues requires timestamp matching.
7. **Container cache race condition** — between checking the in-memory cache and executing a command, the container can die. No recovery path.

### Validation Plan (to reach 90+)

- [ ] Delete scheduler from README/architecture/env vars OR implement it
- [ ] Add integration tests for `POST /api/chat` end-to-end (mock Runtime API, real Redis)
- [ ] Add endpoint tests for all routes in main.py via TestClient
- [ ] Add S3 sync tests (use moto or MinIO testcontainer)
- [ ] Add HEALTHCHECK to Dockerfile; switch to non-root user
- [ ] Create docker-compose.yml with agent-api + runtime-api + redis
- [ ] Make container paths configurable (session storage, process pattern)
- [ ] Add request ID middleware for log correlation
- [ ] Validate Runtime API reachability on startup with clear error message

## License

Apache-2.0
