# /env-setup — Configure and verify infrastructure for post-meeting transcription

You are in **Stage 0: ENV SETUP** for the post-meeting-transcription feature.

## What this feature needs running

| Service | How to check | Required for |
|---------|-------------|-------------|
| bot-manager | `curl http://localhost:8066/health` | Meeting management, transcribe endpoint |
| transcription-service | `curl http://localhost:8083/health` | Whisper transcription (separate GPU compose) |
| MinIO | `curl http://localhost:9000/minio/health/live` | Recording storage |
| Postgres | `psql $POSTGRES_URL -c 'SELECT 1'` | Transcription storage |
| Redis | `redis-cli -u $REDIS_URL ping` | Required by bot-manager |
| tts-service | `curl http://localhost:8002/health` | TTS for speaker bots (collection runs) |
| dashboard | `curl http://localhost:3000` | Playback verification |

## Setup steps

### 1. Create .env

```bash
cp features/post-meeting-transcription/.env.example features/post-meeting-transcription/.env
# Edit values as needed
```

### 2. Verify compose stack

```bash
cd deploy/compose && docker compose ps
```

All services should be running. If not: `docker compose up -d`

### 3. Verify transcription-service (separate GPU stack)

```bash
cd packages/transcription-service && docker compose ps
```

Should show `transcription-api` (nginx) + `transcription-worker-1`. If not: `docker compose up -d`

### 4. Verify TRANSCRIPTION_GATEWAY_URL

The bot-manager must be able to reach the transcription service. Check:

```bash
# From host (dev machine)
curl http://localhost:8083/health

# The bot-manager env var must point to the correct URL
# In docker network: http://transcription-service:80 (via nginx alias on vexa-network)
# From host: http://localhost:8083
```

If bot-manager is in docker and transcription-service is on vexa-network:
- Set `TRANSCRIPTION_GATEWAY_URL=http://transcription-service:80` or `TRANSCRIPTION_SERVICE_URL=http://transcription-service:80` in docker-compose.yml bot-manager env (bot-manager checks `TRANSCRIPTION_GATEWAY_URL` first, falls back to `TRANSCRIPTION_SERVICE_URL`)

### 5. Verify MinIO

```bash
# Check MinIO is accessible
curl http://localhost:9000/minio/health/live

# Check bucket exists
# Via MinIO console: http://localhost:9001 (default: minioadmin/minioadmin)
# Or via mc CLI: mc ls minio/vexa-recordings
```

### 6. Run smoke test

```bash
cd features/post-meeting-transcription/tests
make smoke
```

### 7. Save infra snapshot

After all checks pass, save the current state:

```bash
# Record what's running and with what config
docker compose -f deploy/compose/docker-compose.yml ps > features/post-meeting-transcription/tests/infra-snapshot.md
echo "---" >> features/post-meeting-transcription/tests/infra-snapshot.md
cat features/post-meeting-transcription/.env >> features/post-meeting-transcription/tests/infra-snapshot.md
```
