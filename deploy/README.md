# Deployment

## Why
Vexa supports multiple deployment modes — from single-command local dev to production Kubernetes.

## What

| Mode | Directory | Use case | What you need |
|------|-----------|----------|--------------|
| **Docker Compose** | [compose/](compose/) | Development, self-hosted | Docker + Compose |
| **Lite** | [lite/](lite/) | PaaS, single container | Docker + external Postgres |
| **Helm** | [helm/](helm/) | Production Kubernetes | K8s cluster |

### Docker Compose (development)
Full stack: all services, Postgres, Redis, MinIO. Two modes:
- **Default** — external transcription (no GPU needed). Set `TRANSCRIPTION_SERVICE_URL`.
- **Local GPU** — run transcription-service from the repo. Set `LOCAL_TRANSCRIPTION=true`.

```bash
cp deploy/env/env-example .env
# Edit .env — set TRANSCRIPTION_SERVICE_URL and TRANSCRIPTION_SERVICE_TOKEN
make all
```

### Lite (single container)
All services in one container via supervisord. Only needs external Postgres.
See [lite/README.md](lite/README.md).

### Helm (Kubernetes)
Two charts: `vexa` (full production) and `vexa-lite` (single-pod).
See [helm/README.md](helm/README.md).

## How

### Environment variables
One env-example covers both modes: [env/env-example](env/env-example)

| Variable | Required | Description |
|----------|----------|-------------|
| `TRANSCRIPTION_SERVICE_URL` | Yes | Transcription API endpoint |
| `TRANSCRIPTION_SERVICE_TOKEN` | Yes | Auth token for transcription |
| `LOCAL_TRANSCRIPTION` | No | Set `true` to run GPU transcription locally |
| `REMOTE_DB` | No | Set `true` to use external Postgres |
| `ADMIN_API_TOKEN` | Yes | Admin API auth token |

### Which mode?
| You want... | Use |
|-------------|-----|
| Try it out / develop | `make all` (Docker Compose) |
| Deploy on Railway/Render | Lite |
| Production with scaling | Helm |
