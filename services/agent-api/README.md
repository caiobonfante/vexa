# Agent API

Chat gateway that routes user messages to Claude CLI running inside ephemeral Docker containers. Each user gets an isolated agent container with its own workspace. Sessions persist in Redis so containers can be recreated transparently.

## Key Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/chat` | API key | Send a message, receive SSE stream of agent responses |
| `DELETE` | `/api/chat` | API key | Interrupt an in-progress chat turn |
| `POST` | `/api/chat/reset` | API key | Reset the chat session (keeps workspace files) |
| `GET` | `/api/sessions` | API key | List all sessions for a user |
| `POST` | `/api/sessions` | API key | Create a new named session |
| `PUT` | `/api/sessions/{id}` | API key | Rename a session |
| `DELETE` | `/api/sessions/{id}` | API key | Delete a session |
| `POST` | `/api/webhooks/meeting-completed` | API key | Webhook receiver for post-meeting processing |
| `POST` | `/internal/webhooks/meeting-completed` | None | Internal webhook (Docker network only) |
| `POST` | `/internal/workspace/save` | API key | Sync workspace from container to MinIO |
| `GET` | `/internal/workspace/status` | API key | Check workspace and container status |
| `GET` | `/health` | None | Health check |

## Architecture

- **Containers**: One agent container per user, managed via Docker API. Containers run Claude CLI with tools (Read, Write, Edit, Bash, Glob, Grep).
- **Sessions**: Stored in Redis with 7-day TTL. Session metadata indexed per user with 30-day TTL.
- **Workspaces**: Persisted to MinIO. Injected as context before each chat turn.
- **Meeting events**: Subscribes to Redis Pub/Sub (`bm:meeting:*:status`) to wake agents when meetings start or end.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CHAT_API_PORT` | `8100` | Server port |
| `REDIS_URL` | `redis://redis:6379` | Redis connection URL |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:3001` | Allowed CORS origins |
| `AGENT_IMAGE` | `vexa-agent:dev` | Docker image for agent containers |
| `DOCKER_NETWORK` | `vexa-agentic_vexa_agentic` | Docker network to attach containers to |
| `CONTAINER_PREFIX` | `vexa-agent-` | Container name prefix |
| `IDLE_TIMEOUT` | `300` | Seconds before idle containers are stopped |
| `CLAUDE_CREDENTIALS_PATH` | — | Host path to Claude credentials file |
| `CLAUDE_JSON_PATH` | — | Host path to claude.json config |
| `MINIO_ENDPOINT` | `http://minio:9000` | MinIO endpoint |
| `MINIO_ACCESS_KEY` | `vexa-access-key` | MinIO access key |
| `MINIO_SECRET_KEY` | `vexa-secret-key` | MinIO secret key |
| `MINIO_BUCKET` | `vexa-agentic` | MinIO bucket for workspaces |
| `RUNTIME_API_URL` | `http://runtime-api:8090` | Runtime API URL |
| `DEFAULT_MODEL` | — | Default Claude model override |
| `LOG_LEVEL` | `INFO` | Log level |

## Running Locally

```bash
cd services/agent-api
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload
```

Requires Redis and Docker daemon access. Agent containers need the Claude credentials mounted.
