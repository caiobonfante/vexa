# Environment Variable Examples

## Why
Each deployment profile needs different env vars (GPU settings, transcription URLs, model sizes). Example files provide working defaults for each profile.

## What

| File | Profile | GPU required? | Notes |
|------|---------|---------------|-------|
| [env-example.remote](env-example.remote) | Remote transcription | No | Recommended for first setup |
| [env-example.cpu](env-example.cpu) | Local CPU Whisper | No | Slower, development only |
| [env-example.gpu](env-example.gpu) | Local GPU Whisper | Yes | Best quality, needs NVIDIA GPU |

## How

Copy the appropriate file to `.env` at the repo root:

```bash
cp deploy/env/env-example.remote .env
# Edit .env with your values
make all
```

Or use the Makefile helper:

```bash
make env TRANSCRIPTION=remote   # copies env-example.remote -> .env
make env TRANSCRIPTION=cpu      # copies env-example.cpu -> .env
make env TRANSCRIPTION=gpu      # copies env-example.gpu -> .env
```

For the full variable reference, see [Deployment Guide](https://docs.vexa.ai/deployment).
