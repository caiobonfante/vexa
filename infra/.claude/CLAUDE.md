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

## Logging
Append meaningful findings to `/home/dima/dev/vexa/test.log`:
- Format: `[timestamp] [agent-name] LEVEL: message`
- Levels: PASS (summary only), FAIL, DEGRADED, ROOT CAUSE, SURPRISING
- Don't spam — one line per finding, not per check
