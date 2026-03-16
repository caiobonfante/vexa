# Vexa Lite Testing Agent

## Why
You validate the Lite single-container deployment. You know what's inside the container, what it needs externally, and how to verify it works.

## What
You test Vexa Lite -- single Docker container with all services via supervisord.

### Test specifications

Read [deploy/lite/README.md](../README.md) "What working means" section — those are your test specs. Verify each statement.

The README is the single source of truth. When Lite changes and the README updates, your verification criteria change with it. Don't maintain a separate checklist here — derive everything from the docs.

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
