# Agent Runtime

## Why

Running an LLM agent inside a container is the easy part. The hard parts are everything around it: routing user messages to the right container, resuming sessions after container restarts, syncing workspace files so work survives reboots, and scheduling future jobs without a separate cron service. Every AI product that wants stateful agents in containers solves these problems from scratch. Agent Runtime packages the application layer — chat routing, sessions, workspace persistence, scheduling — so you wire it to [Runtime API](../runtime-api/) for container ops and get a complete agent backend.

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
uvicorn agent_runtime.main:app --host 0.0.0.0 --port 8100
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
│ Agent Runtime │
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
2. Agent Runtime ensures agent container is running (via Runtime API)
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

Agent Runtime handles the **application layer** — chat routing, sessions, workspaces, scheduling. It delegates all **container operations** (create, stop, idle management) to [Runtime API](../runtime-api/).

```
Agent Runtime = what the agent does
Runtime API   = where the agent runs
```

## License

Apache-2.0
