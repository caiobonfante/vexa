# Scheduler Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules
> Development cycle: [features/README.md](../../README.md#spec-driven-features) — research, spec, build & test

## Mission

Build the reliable execution backbone for all time-triggered actions in Vexa. Every "do X at time T" flows through the scheduler. Calendar auto-join, webhook retry, deferred transcription, recording cleanup — one system, one set of guarantees.

## Development cycle

This is a **spec-driven feature** — see [features/README.md](../../README.md#spec-driven-features).

### Current stage: BUILD & TEST (Phase 1)

**Research:** Complete (scheduler design proven, Redis sorted set approach validated).
**Implementation:** Core library done (16/16 tests pass). Need to wire executor + add REST API.

### Priority batches

| Batch | Items | Status |
|-------|-------|--------|
| Core library | `schedule_job()`, executor, retry, idempotency, crash recovery | Done (16/16 tests) |
| Phase 1 | Wire executor into bot-manager startup | Not started |
| Phase 2 | REST API (`POST/GET/DELETE /schedule`) + gateway proxy | Not started |
| Phase 3 | Calendar-service integration | Not started |
| Phase 4 | Migrate webhook retry to scheduler | Not started |
| Phase 5 | Priorities, rate limiting, recurring jobs, dashboard | Not started |

## Scope

You own the scheduler infrastructure: job scheduling, execution, retry, idempotency, crash recovery, and the REST API. You don't own what gets scheduled — calendar, webhooks, and other features are consumers.

### Gate (local)

| Check | Pass | Fail |
|-------|------|------|
| Unit tests | 16/16 pass | Any failure |
| Job scheduling | `schedule_job()` creates job in Redis sorted set | Job not in Redis |
| Idempotency | Same `idempotency_key` returns existing job, doesn't duplicate | Two jobs created |
| Execution | Due job fires HTTP request within 5s of target time | Job not fired or >10s late |
| Retry | Failed job re-queued with backoff delay | Job dropped on first failure |
| Crash recovery | Orphaned executing jobs re-queued on startup | Jobs lost on crash |
| Cancellation | `cancel_job()` removes from queue, stores in history | Job still fires after cancel |
| Callbacks | `on_success`/`on_failure` URLs called with result | No callback fired |
| REST API | `POST/GET/DELETE /schedule` work through gateway | Endpoints missing or broken |

### Edges

**Provides to:**
- calendar-integration (schedule bot-join before meetings)
- webhooks (retry failed deliveries — Phase 4)
- post-meeting-transcription (trigger deferred processing)
- MCP (expose `schedule_api_call` tool)
- Any feature that needs "do X at time T"

**Depends on:**
- Redis (sorted set storage, crash recovery)
- api-gateway (proxies REST endpoints)
- Target APIs (whatever the scheduled jobs call)

**Data flow:**
```
Producer → schedule_job(redis, spec) → Redis ZADD
Executor → Redis ZRANGEBYSCORE → HTTP call → history + callback
REST API → POST /schedule → schedule_job() → same flow
```

### Counterparts
- **Consumers:** calendar-integration, webhooks, post-meeting-transcription, MCP
- **Infrastructure:** Redis, api-gateway
- **Similar pattern:** `webhook_retry_worker.py` (will be migrated to scheduler in Phase 4)

## Key code locations

| Component | File | Status |
|-----------|------|--------|
| Core API | `libs/shared-models/shared_models/scheduler.py` | Done |
| Executor | `libs/shared-models/shared_models/scheduler_worker.py` | Done |
| Unit tests | `libs/shared-models/shared_models/test_scheduler.py` | 16/16 pass |
| REST endpoints | TBD (bot-manager or dedicated service) | Not started |
| E2E tests | `features/scheduler/tests/test-scheduler.sh` | Not started |

## How to test

```bash
# Unit tests (instant, no services needed)
cd libs/shared-models
python3 -m pytest shared_models/test_scheduler.py -v

# Feature tests (needs running services)
cd features/scheduler/tests
make test
```

## Reliability guarantees

| Scenario | Handling |
|----------|----------|
| Service restart mid-execution | `scheduler:executing` hash tracks in-flight jobs → re-queued on startup |
| Duplicate execution | `ZREM` returns 0 if another worker took it → skip |
| API call fails (5xx/429) | Retry with exponential backoff per job config |
| API call fails (4xx) | Fail immediately — client error, don't retry |
| API call hangs | HTTP timeout (default 30s) → counts as failure |
| Redis restart | Jobs in sorted set persisted (RDB/AOF) |
| Duplicate scheduling | `idempotency_key` checked before insert |
| Clock skew | Jobs execute within POLL_INTERVAL (~5s) of target |

## Critical findings
Save to `tests/findings.md`.
