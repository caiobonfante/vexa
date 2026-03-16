# Deployment

## Why
Vexa supports 3 deployment modes for different needs -- development, PaaS, and production Kubernetes.

## What

| Mode | Directory | Use case | What you need |
|------|-----------|----------|--------------|
| **Docker Compose** | [compose/](compose/) | Development, self-hosted | Docker + Compose |
| **Lite** | [lite/](lite/) | PaaS, single container | Docker + external Postgres |
| **Helm** | [helm/](helm/) | Production Kubernetes | K8s cluster |

### Docker Compose (development)
Full stack: all services, Postgres, Redis, transcription. Three profiles:
- `remote` -- external transcription (no GPU needed)
- `cpu` -- local Whisper on CPU
- `gpu` -- local Whisper on GPU

```bash
cp deploy/env/env-example.remote .env
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
All env vars documented in [env/](env/). Example files:
- [env-example.remote](env/env-example.remote) -- recommended for first setup
- [env-example.cpu](env/env-example.cpu) -- local CPU transcription
- [env-example.gpu](env/env-example.gpu) -- local GPU transcription

### Which mode?
| You want... | Use |
|-------------|-----|
| Try it out / develop | `make all` (Docker Compose) |
| Deploy on Railway/Render | Lite |
| Production with scaling | Helm |
