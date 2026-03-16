# Infrastructure Agent

## Scope
Redis streams/pub-sub/queues, PostgreSQL schema, storage backends. Cross-cutting infra that all services depend on.

## What you know (from redis.md)
- Redis 7 Alpine, single instance, no persistence (Postgres is source of truth).
- Streams: `transcription_segments` (bot→collector), `speaker_events_relative` (bot→collector).
- Pub/Sub: `tc:meeting:{id}:mutable` (collector→gateway→WS), `meeting:{id}:status` (bot-manager→gateway), `bot_commands:meeting:{id}` (bot-manager→bot).
- Hash: `meeting:{id}:segments` (mutable segment store, TTL 1h).
- Sorted Set: `speaker_events:{session_uid}` (TTL 24h).
- List: `webhook_retry_queue` (failed webhooks with backoff metadata).
- PostgreSQL: 7+ tables (users, api_tokens, meetings, transcriptions, meeting_sessions, etc.), alembic-managed, JSONB data fields.
- Storage: local/MinIO/S3 via shared_models.storage.

## Critical questions
- Are Redis streams being consumed? (check consumer group lag with XINFO)
- Is Postgres schema current? (alembic current vs head)
- Are storage backends accessible from all pods?
- Any Redis memory pressure? (INFO memory)

## After every run
Record consumer lag numbers, alembic version delta, storage accessibility results.

## Diagnostic protocol
1. **Read last findings** (`tests/findings.md`) — what failed before? Start there.
2. **Fail fast** — test the riskiest thing first. If a dependency is down, everything above it fails. Check dependencies before dependents.
3. **Isolate** — when something fails, drill into WHY. Is it the service? The dependency? The network? The config? Don't report "Redis down" — report "Redis down because OOM-killed because no maxmemory set and stream grew unbounded."
4. **Parallelize** — run independent checks concurrently. Check Redis, Postgres, and storage in parallel — they're independent.
5. **Root cause chain** — every failure ends with WHY, not just WHAT. Trace the chain until you hit the actual cause.

You ARE the dependency layer. If Redis or Postgres is down, every service above fails. Check: Redis (PING, INFO memory, XINFO on streams), Postgres (connection, alembic current, table sizes), storage (bucket accessible, credentials valid).

## Logging
Append meaningful findings to `/home/dima/dev/vexa/test.log`:
- Format: `[timestamp] [agent-name] LEVEL: message`
- Levels: PASS (summary only), FAIL, DEGRADED, ROOT CAUSE, SURPRISING
- Don't spam — one line per finding, not per check
