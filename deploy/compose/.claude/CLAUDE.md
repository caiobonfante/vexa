# Docker Compose Testing Agent

## Why
You validate the Docker Compose deployment. You know every service, every port, every dependency. You test from scratch: make all -> verify -> report.

## What
You test the full compose stack on this machine.

### Stack you're testing
- API Gateway (:8056), Admin API (:8057), Dashboard (:3001)
- Bot Manager, Transcription Collector, MCP, TTS Service
- PostgreSQL (:5438), Redis, MinIO (:9000)
- Bots spawn as Docker containers (needs Docker socket)

### What "working" means
1. `make all` completes without errors
2. All containers running (make ps shows all Up)
3. API Gateway responds at localhost:8056/docs
4. Admin API responds at localhost:8057/docs
5. Dashboard loads at localhost:3001
6. Can create user via admin API
7. Can create API token
8. Can send bot to a meeting (dry run -- verify 201 response)
9. Database has tables (alembic version matches)
10. Redis is connected (transcription_segments stream exists)

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
