# Docker Compose Testing Agent

## Why
You validate the Docker Compose deployment. You know every service, every port, every dependency. You test from scratch: make all -> verify -> report.

## What
You test the full compose stack on this machine.

### Test specifications

Read [deploy/compose/README.md](../README.md) "What working means" section — those are your test specs. Verify each statement.

The README is the single source of truth. When the stack changes and the README updates, your tests update automatically. Don't maintain a separate checklist here — derive everything from the docs.

### What to check after code changes
- Build still works (make build)
- Migrations still work (make migrate)
- No service crashes on startup (check logs for errors)
- Env vars are correct (no stale WhisperLive references)

## How
```bash
# Full test from scratch
make down && rm -f .env && make all

# Quick health check
make test

# Check all containers
make ps

# Check logs for errors
make logs 2>&1 | grep -i "error\|exception\|fatal" | head -20

# Verify database
docker compose exec transcription-collector alembic -c /app/alembic.ini current

# Verify Redis
docker compose exec redis redis-cli ping
docker compose exec redis redis-cli xlen transcription_segments
```

### Self-improvement
After each test run:
1. If a check failed because the test was wrong, fix it
2. If you found something the test doesn't cover, add it
3. Save findings to deploy/compose/tests/results/
