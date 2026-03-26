# Runtime API

## Why

You need to spawn containers on demand — AI agent sandboxes, browser sessions, code runners, dev environments. The options are: Fly Machines (proprietary, not self-hosted), Kubernetes Jobs (requires K8s, no idle management, no callbacks), Docker Compose (no API, no per-user limits), or E2B (proprietary, not self-hosted).

None of them give you a self-hosted REST API with idle management, lifecycle callbacks, and per-tenant concurrency that works across Docker, Kubernetes, and plain processes from the same interface.

Runtime API fills that gap. `POST /containers` with a profile name and a callback URL. Get a managed container back. It idles out automatically, fires a webhook when it exits, and enforces per-user limits. Switch from Docker in dev to Kubernetes in prod by changing one environment variable.

**Why not build it yourself?** Container lifecycle code is deceptively simple until you handle: orphaned containers after crashes (state reconciliation on startup), idle detection across restarts (Redis-backed timers), callback delivery with retry (exponential backoff), graceful shutdown that doesn't kill active work, and per-user concurrency enforcement across a distributed fleet. That's what the 2400 lines here do.

## What

- **REST API** for container lifecycle — create, inspect, stop, list, exec
- **Profile system** — declarative YAML templates for container types
- **Three backends** — Docker, Kubernetes, and local process
- **Idle management** — automatic cleanup of inactive containers
- **Lifecycle callbacks** — webhook notifications on container state changes
- **Per-tenant concurrency** — configurable limits per user and profile
- **Redis state** — fast queries with backend reconciliation on startup

## How

### Quickstart

### Docker Compose (recommended)

```bash
curl -O https://raw.githubusercontent.com/vexa-ai/runtime-api/main/docker-compose.yml
docker compose up -d
```

### From source

```bash
git clone https://github.com/vexa-ai/runtime-api.git
cd runtime-api
pip install -e .
uvicorn runtime_api.main:app --host 0.0.0.0 --port 8090
```

Requires Redis (`redis://localhost:6379`) and Docker daemon access.

### Create a container

```bash
# Create a container from a profile
curl -X POST http://localhost:8090/containers \
  -H "Content-Type: application/json" \
  -d '{
    "profile": "worker",
    "user_id": "user-123",
    "callback_url": "http://my-service:8080/hooks/container",
    "metadata": {"job_id": "abc"}
  }'
```

### List containers

```bash
curl http://localhost:8090/containers?profile=worker&user_id=user-123
```

### Stop a container

```bash
curl -X DELETE http://localhost:8090/containers/worker-abc123
```

### Heartbeat (reset idle timer)

```bash
curl -X POST http://localhost:8090/containers/worker-abc123/touch
```

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/containers` | Create and start a container |
| `GET` | `/containers` | List containers (filter by `user_id`, `profile`) |
| `GET` | `/containers/{name}` | Inspect container (status, ports, metadata) |
| `DELETE` | `/containers/{name}` | Stop and remove container |
| `POST` | `/containers/{name}/touch` | Heartbeat — reset idle timer |
| `POST` | `/containers/{name}/exec` | Execute command inside container |
| `GET` | `/containers/{name}/wait` | Long-poll until target state reached |
| `GET` | `/profiles` | List available container profiles |
| `GET` | `/health` | Health check with container counts |

## Profiles

Profiles are declarative container templates defined in YAML. Reference them by name when creating containers.

```yaml
# profiles.yaml
profiles:
  worker:
    image: my-worker:latest
    resources:
      cpu_limit: "1000m"
      memory_limit: "2Gi"
    idle_timeout: 900        # stop after 15min idle
    auto_remove: true
    max_per_user: 5
    ports:
      "8080/tcp": {}

  sandbox:
    image: code-sandbox:latest
    command: ["sleep", "infinity"]
    resources:
      cpu_limit: "2000m"
      memory_limit: "2Gi"
      shm_size: 2147483648   # 2GB
    idle_timeout: 600        # 10min
    max_per_user: 1          # one sandbox per user
    ports:
      "8080/tcp": {}
```

Hot-reload: `kill -HUP <pid>` to reload profiles without restart.

## Backends

Runtime API supports three orchestration backends, selected via `ORCHESTRATOR_BACKEND` environment variable:

| Backend | Env Value | Use Case |
|---------|-----------|----------|
| **Docker** | `docker` | Local development, single-host deployment |
| **Kubernetes** | `kubernetes` | Production — pods, RBAC, resource limits, node selectors |
| **Process** | `process` | Lightweight — child processes, no container runtime needed |

### Backend interface

All backends implement the same abstraction:

```
create(spec) → container_id
stop(name, timeout) → bool
remove(name) → bool
inspect(name) → ContainerInfo | None
list(labels) → ContainerInfo[]
exec(name, cmd) → AsyncIterator[bytes]
startup() → None
shutdown() → None
listen_events(on_exit) → None
```

## Lifecycle Callbacks

Pass a `callback_url` when creating a container. Runtime API POSTs to it on state transitions:

```json
{
  "container_id": "abc123def",
  "name": "worker-abc123",
  "profile": "worker",
  "status": "stopped",
  "exit_code": 0,
  "metadata": {"job_id": "abc"}
}
```

Callbacks fire on: `stopped` (clean exit or idle timeout), `failed` (non-zero exit code). Retries with exponential backoff (default: 1s, 5s, 30s).

## Comparison

| | Runtime API | Fly Machines | K8s Jobs | Docker Compose | E2B |
|---|---|---|---|---|---|
| REST API | Yes | Yes | Via kubectl | No | Yes |
| Container profiles | Yes | No | No | No | Templates |
| Idle management | Yes | Yes (auto-stop) | No | No | Yes |
| Lifecycle callbacks | Yes | No | Limited | No | No |
| Per-tenant concurrency | Yes | No | No | No | Yes |
| Self-hosted | Yes | No | Yes | Yes | No |
| Open source | Yes | No | Yes | Yes | No |
| No K8s required | Yes | Yes | No | Yes | Yes |
| Multi-backend | Yes | No | K8s only | Docker only | No |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ORCHESTRATOR_BACKEND` | `docker` | Backend: `docker`, `kubernetes`, or `process` |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `PROFILES_PATH` | `profiles.yaml` | Path to profiles config |
| `IDLE_CHECK_INTERVAL` | `30` | Seconds between idle checks |
| `CALLBACK_RETRIES` | `3` | Max callback delivery attempts |
| `CALLBACK_BACKOFF` | `1,5,30` | Backoff delays in seconds |
| `API_KEYS` | _(empty)_ | Comma-separated API keys (empty = no auth) |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |
| `LOG_LEVEL` | `INFO` | Log level |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8090` | Server port |

### Docker backend

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCKER_HOST` | `unix:///var/run/docker.sock` | Docker daemon socket |
| `DOCKER_NETWORK` | `bridge` | Docker network for containers |

### Kubernetes backend

| Variable | Default | Description |
|----------|---------|-------------|
| `K8S_NAMESPACE` | `default` | Kubernetes namespace (falls back to `POD_NAMESPACE`) |
| `K8S_SERVICE_ACCOUNT` | _(empty)_ | Service account for pods |
| `K8S_IMAGE_PULL_POLICY` | `IfNotPresent` | Image pull policy |
| `K8S_IMAGE_PULL_SECRET` | _(empty)_ | Image pull secret name |

### Process backend

| Variable | Default | Description |
|----------|---------|-------------|
| `PROCESS_LOGS_DIR` | `/var/log/containers` | Directory for process logs |
| `PROCESS_REAPER_INTERVAL` | `30` | Seconds between reaper checks |

## Architecture

```
                    ┌──────────────┐
                    │  Your App    │
                    │              │
                    │ POST /containers
                    │ GET  /containers
                    │ DELETE /containers/{name}
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Runtime API │
                    │              │
                    │ • profiles   │
                    │ • state      │
                    │ • idle mgmt  │
                    │ • callbacks  │
                    │ • concurrency│
                    └──────┬───────┘
                           │
                  ┌────────┼────────┐
                  │        │        │
            ┌─────▼──┐ ┌──▼───┐ ┌──▼──────┐
            │ Docker │ │ K8s  │ │ Process │
            │ socket │ │ pods │ │ child   │
            └────────┘ └──────┘ └─────────┘
```

## Use Cases

- **AI agent sandboxes** — give agents their own containers with lifecycle management
- **Browser automation farms** — manage browser pools with CDP access and idle cleanup
- **Dev environments** — on-demand coding containers with workspace persistence
- **CI/CD runners** — ephemeral build containers with per-tenant limits
- **Code execution** — sandboxed code runners with timeout enforcement

## License

Apache-2.0
