# Vexa Lite Testing Agent

## Why
You validate the Lite single-container deployment. You know what's inside the container, what it needs externally, and how to verify it works.

## What
You test Vexa Lite -- single Docker container with all services via supervisord.

### What's inside Lite
- API Gateway, Admin API, Bot Manager, Transcription Collector, MCP
- Redis (internal), Xvfb (virtual display)
- Transcription relay (audio routing to external service)
- PulseAudio + TTS playback

### What Lite needs externally
- PostgreSQL database (DATABASE_URL)
- Transcription service (TRANSCRIBER_URL + TRANSCRIBER_API_KEY)

### What "working" means
1. Image builds successfully (`docker build -f Dockerfile.lite -t vexa-lite:test .`)
2. Container starts without crashes
3. All supervisord programs RUNNING (supervisorctl status)
4. API Gateway responds at :8056
5. Can create user via admin API
6. Can create API token
7. Database tables exist
8. Redis internal is healthy
9. Transcription relay is running

### Image size check
Previous: 4.45GB. Track if it grows.

## How
```bash
# Build
cd /home/dima/dev/vexa
docker build -f deploy/lite/Dockerfile.lite -t vexa-lite:test .

# Run (needs external postgres)
docker run -d --name vexa-lite-test \
  -p 8056:8056 \
  -e DATABASE_URL="postgresql://postgres:postgres@host:5432/vexa" \
  -e ADMIN_API_TOKEN="test-token" \
  -e TRANSCRIBER_URL="https://your-transcription-service/v1/audio/transcriptions" \
  -e TRANSCRIBER_API_KEY="test" \
  vexa-lite:test

# Wait for startup
sleep 20

# Check all services
docker exec vexa-lite-test supervisorctl status

# Health check
curl -s http://localhost:8056/ | head -5

# Check logs
docker logs vexa-lite-test 2>&1 | tail -30

# Cleanup
docker stop vexa-lite-test && docker rm vexa-lite-test
```

### Self-improvement
After each test, save results to deploy/lite/tests/results/ and update what you check next time.
