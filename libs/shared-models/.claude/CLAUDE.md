# Shared Models Agent

## Scope
ORM models, Pydantic schemas, database sessions, storage abstraction, webhook delivery, token scoping. Used by all Python services.

## What you know
- models.py: User, APIToken, Meeting (status: requested→joining→awaiting_admission→active→completed→failed), Transcription, MeetingSession, plus JSONB `data` fields on User and Meeting.
- schemas.py: request/response schemas, Platform enum, voice_agent_enabled defaults to False.
- token_scope.py: prefix-based scoping — vxa_bot_, vxa_tx_, vxa_user_, vxa_admin_. Enforced in api-gateway, bot-manager, admin-api.
- webhook_delivery.py: durable delivery with Redis retry queue, exponential backoff.
- webhook_retry_worker.py: BRPOP from webhook_retry_queue, re-deliver with backoff.
- storage.py: S3/MinIO/local filesystem abstraction.
- database.py: SQLAlchemy session factory.
- test_token_scope.py, test_webhook_delivery_history.py, test_webhook_retry.py: existing tests.

## Critical questions
- Do models match actual DB schema? (run alembic check)
- Are token scope prefixes consistent across all 3 enforcing services?
- Does webhook retry actually redeliver? (test_webhook_retry.py passing?)
- Is storage backend accessible from all services that import it?

## After every run
Run existing tests: `pytest test_token_scope.py test_webhook_delivery_history.py test_webhook_retry.py`. Update with results.

## Diagnostic protocol
1. **Read last findings** (`tests/findings.md`) — what failed before? Start there.
2. **Fail fast** — test the riskiest thing first. If a dependency is down, everything above it fails. Check dependencies before dependents.
3. **Isolate** — when something fails, drill into WHY. Is it the model? The migration? The connection? Don't report "test failed" — report "test failed because token_scope.py expects vxa_admin_ prefix but admin-api sends admin_."
4. **Parallelize** — run independent checks concurrently. Don't wait for DB tests before running unit tests.
5. **Root cause chain** — every failure ends with WHY, not just WHAT. Trace the chain until you hit the actual cause.

Dependencies to check first: Postgres (alembic current vs head — schema drift?), Redis (webhook retry queue). If models don't match DB, check alembic migration state before editing models.

## Logging
Append meaningful findings to `/home/dima/dev/vexa/test.log`:
- Format: `[timestamp] [agent-name] LEVEL: message`
- Levels: PASS (summary only), FAIL, DEGRADED, ROOT CAUSE, SURPRISING
- Don't spam — one line per finding, not per check
