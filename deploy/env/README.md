# Environment Variables

## Why

Twelve services with different ports, database URLs, API tokens, and feature flags — getting one wrong means silent failures or services that can't find each other. A single env-example with comments is the fastest path from "I cloned the repo" to "everything is running." Without it, you're reading a dozen docker-compose entries and guessing which variables matter.

## What

One example file covers both deployment modes:

| File | Description |
|------|-------------|
| [env-example](env-example) | All variables with sensible defaults and comments |

Two modes:
- **Default** — external transcription. Set `TRANSCRIPTION_SERVICE_URL`.
- **Local GPU** — set `LOCAL_TRANSCRIPTION=true` to also start transcription-service.

## How

```bash
cp deploy/env/env-example .env
# Edit .env — set TRANSCRIPTION_SERVICE_URL and TRANSCRIPTION_SERVICE_TOKEN
make all
```

For the full variable reference, see [Deployment Guide](https://docs.vexa.ai/deployment).
