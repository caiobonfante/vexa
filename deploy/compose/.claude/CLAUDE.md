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

### After every test run
1. Update the README if specs were unclear
2. Add unexpected findings to `tests/findings.md`
3. Note what you couldn't test and why
4. The goal: each run makes the docs better, which makes the next run better

## Orchestration

You are the root of the test tree. You test infrastructure and API directly. For deep service testing, dispatch background agents to each service folder.

The full test playbook is in [commands/test.md](commands/test.md) — 7 phases, 3 modes (quick/standard/full).

### Constraints
- Background agents can only curl exposed ports + read files (no docker compose exec)
- You handle container-level checks (compose exec, logs, restart counts)
- Max 3 concurrent background agents
- Waves ordered by dependency: infra → foundation → dependent → frontend

### Findings format
Each service saves tests/findings.md. You aggregate into tests/results/report-{timestamp}.md.

### Self-improvement
If a service agent's findings contradict the README spec, update the README. Findings bubble up; specs flow down.
