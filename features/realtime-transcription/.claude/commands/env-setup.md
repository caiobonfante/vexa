# /env-setup — Set up infrastructure for realtime transcription

You are in **Stage 0: ENV SETUP** for the realtime-transcription feature.

Read the generic stage protocol first: `/.claude/commands/env-setup.md`

## Feature-specific context

This feature needs these services running:

| Service | What for | Health check |
|---------|---------|-------------|
| transcription-service | Whisper inference (faster-whisper) | `curl $TRANSCRIPTION_URL/../health` |
| tts-service | Generate WAVs from scripts for collection runs | `curl $TTS_URL/../health` |
| redis | Segment publishing + pub/sub | `redis-cli PING` |
| postgres | Segment persistence | `psql -c 'SELECT 1'` |
| bot-manager | Bot lifecycle | `curl $API_GATEWAY_URL/health` |
| api-gateway | REST + WebSocket delivery | `curl $API_GATEWAY_URL/health` |

## .env.example location

`features/realtime-transcription/.env.example` — copy to `.env` and fill in.

Key variables to get right:
- `TRANSCRIPTION_URL` — must point to a running transcription-service with the correct model
- `TRANSCRIPTION_TOKEN` — must match the transcription-service's `API_TOKEN`
- `MODEL_SIZE` — should match production unless explicitly testing a different model
- `PLATFORM` — `ms-teams` or `google-meet`, affects which caption/speaker detection path is used

## Smoke test

```bash
cd features/realtime-transcription/tests
make smoke    # sends short-sentence.wav through pipeline, verifies output
```

If smoke fails, check in order:
1. Is transcription-service reachable? `curl $TRANSCRIPTION_URL/../health`
2. Is the token correct? 401 = wrong token
3. Is the model loaded? First request may take 30s+ for model load
4. Is the compose stack up? `docker ps` from `deploy/compose/`

## Infra snapshot

Save to `features/realtime-transcription/tests/infra-snapshot.md`. Include the full `.env` (redact tokens) and all health check results.
