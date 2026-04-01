# Scheduler

> **Confidence: 0** — RESET after architecture refactoring. Scheduler moved from shared-models to runtime-api (shared-models being deleted). Wired into runtime-api main.py but never tested live.
> **Tested:** Job scheduling, atomic execution (no duplicates), retry with backoff, crash recovery, cancellation, on_success/on_failure callbacks, idempotency keys.
> **Not tested:** Executor not wired into running services. REST API not built. No E2E test through gateway.
> **Contributions welcome:** Wire executor into runtime-api startup, REST API endpoints (POST/GET/DELETE /schedule), calendar-service integration.

## Why

Single backbone for all time-triggered actions. Today each is ad-hoc: webhook retry has its own Redis list, deferred transcription is manual, calendar auto-join doesn't exist. The scheduler unifies all of these: **"call this API at this time, reliably."**

**Design decisions:**
- Redis sorted sets (not in-process timers like OpenClaw's asyncio approach) — crash-safe, persistent
- `on_success`/`on_failure` callbacks enable container chaining without a DSL — meeting → agent → worker pipelines
- HTTP-based execution — scheduler doesn't know what it's calling, just fires HTTP requests with retry

**Example pipeline:**

```
Schedule: "0 9 * * 1-5" (weekdays 9am)
  → Spawn browser → join standup → transcribe
  → on_success: spawn agent → summarize → post to Slack
  → on_success: spawn worker → webhook to CRM
  → All containers die. Zero cost until tomorrow.
```

## What

A generic, bullet-proof job scheduler backed by Redis sorted sets. Two components:

1. **Schedule API** — accepts "when" (timestamp) + "what" (HTTP call spec) + "how" (retry, idempotency, callbacks)
2. **Executor** — polls for due jobs, fires HTTP calls, retries on failure, tracks results

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Producers                             │
│  calendar-service  │  meeting-api  │  admin-api  │ MCP  │
└────────┬───────────┴───────┬───────┴──────┬──────┴──────┘
         │                   │              │
         ▼                   ▼              ▼
┌─────────────────────────────────────────────────────────┐
│                   Schedule API                           │
│  POST /schedule  — create job                            │
│  GET  /schedule  — list jobs                             │
│  GET  /schedule/{id} — get job                           │
│  DELETE /schedule/{id} — cancel job                      │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              Redis Sorted Set                            │
│  ZADD scheduler:jobs <execute_at> <job_json>             │
│  Score = unix timestamp → natural time ordering          │
│  ZRANGEBYSCORE -inf <now> → get due jobs                 │
│  ZREM → atomic pop (prevents duplicate execution)        │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    Executor                               │
│  Background loop (every 5s):                             │
│    1. Pop due jobs from sorted set                       │
│    2. Track in scheduler:executing hash (crash recovery)  │
│    3. Fire HTTP request with timeout                      │
│    4. On success → history + callback                     │
│    5. On failure → retry with backoff OR fail + callback  │
│    6. Remove from executing, store in history             │
└─────────────────────────────────────────────────────────┘
```

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **scheduler.py** | `services/runtime-api/runtime_api/scheduler.py` | Core API: `schedule_job()`, `cancel_job()`, `list_jobs()`, `get_job()` |
| **scheduler_api.py** | `services/runtime-api/runtime_api/scheduler_api.py` | REST endpoints for scheduling |
| **test_scheduler.py** | `services/runtime-api/tests/test_scheduler.py` | Unit tests |

### Job spec

Every scheduled job is a self-contained JSON blob:

```json
{
  "job_id": "job_a1b2c3d4e5f6g7h8",
  "execute_at": 1774224000,
  "created_at": 1774220400,
  "status": "pending",

  "request": {
    "method": "POST",
    "url": "http://api-gateway:8000/bots",
    "headers": {"X-API-Key": "vxa_bot_..."},
    "body": {"meeting_url": "https://meet.google.com/abc-defg-hij"},
    "timeout": 30
  },

  "retry": {
    "max_attempts": 3,
    "backoff": [30, 120, 300],
    "attempt": 0
  },

  "metadata": {
    "source": "calendar",
    "user_id": 1,
    "meeting_title": "Team Standup"
  },

  "callback": {
    "on_success": "http://calendar-service:8071/internal/bot-scheduled",
    "on_failure": "http://calendar-service:8071/internal/bot-failed"
  },

  "idempotency_key": "cal_evt123_bot"
}
```

### Key behaviors

- **Time precision**: jobs execute within 5 seconds of target time (POLL_INTERVAL)
- **Atomic execution**: `ZREM` returns 0 if another worker already took the job — no duplicates
- **Idempotency**: optional `idempotency_key` prevents scheduling the same job twice
- **Retry with backoff**: configurable per-job (default: 30s, 2min, 5min, 3 attempts)
- **Crash recovery**: in-flight jobs tracked in `scheduler:executing` hash, re-queued on startup
- **Callbacks**: optional `on_success`/`on_failure` URLs notified with job result
- **History**: completed/failed jobs stored in `scheduler:history` hash (7-day TTL)
- **Cancellation**: `DELETE /schedule/{id}` removes from queue, stores in history as cancelled

### Data flow

```
Producer (calendar sync, admin action, MCP tool call)
  │
  ▼
schedule_job(redis, spec)
  │ validates spec
  │ checks idempotency_key (skip if duplicate)
  │ ZADD scheduler:jobs <execute_at> <job_json>
  │
  ▼
Redis sorted set (scheduler:jobs)
  │ score = execute_at unix timestamp
  │
  ▼ (executor polls every 5s)
ZRANGEBYSCORE scheduler:jobs -inf <now>
  │ returns all due jobs
  │
  ▼ (for each due job)
ZREM scheduler:jobs <job_json>  ← atomic, prevents duplicate execution
  │
  ▼
HSET scheduler:executing <job_id> <job_json>  ← crash recovery tracking
  │
  ▼
HTTP request (method, url, headers, body, timeout)
  │
  ├─ 2xx/3xx → completed
  │   ├─ HDEL scheduler:executing
  │   ├─ HSET scheduler:history
  │   └─ POST callback.on_success
  │
  ├─ 5xx/429/timeout → retry?
  │   ├─ attempt < max_attempts → ZADD with backoff delay
  │   └─ attempt >= max_attempts → failed
  │       ├─ HDEL scheduler:executing
  │       ├─ HSET scheduler:history
  │       └─ POST callback.on_failure
  │
  └─ 4xx → failed immediately (client error, don't retry)
      ├─ HDEL scheduler:executing
      ├─ HSET scheduler:history
      └─ POST callback.on_failure
```

### Redis keys

| Key | Type | Purpose | TTL |
|-----|------|---------|-----|
| `scheduler:jobs` | Sorted Set | Pending jobs, scored by execute_at | None (persistent) |
| `scheduler:executing` | Hash | In-flight jobs (crash recovery) | None |
| `scheduler:history` | Hash | Completed/failed/cancelled jobs | 7 days |
| `scheduler:idem:{key}` | String | Idempotency dedup | 7 days |

### Consumers

| Feature | What it schedules | When |
|---------|-------------------|------|
| **bot-lifecycle** | `DELETE /bots/{platform}/{meeting_id}` — max_bot_time enforcement | Bot creation + max_bot_time (default 2h). Cancelled if bot exits normally. |
| **calendar-integration** | `POST /bots` with meeting URL | 1 min before calendar event |
| **webhooks** | Retry failed webhook delivery | Backoff schedule (1m, 5m, 30m, 2h) |
| **post-meeting-transcription** | `POST /meetings/{id}/transcribe` | Meeting end + 30s |
| **recording-cleanup** | `DELETE /recordings/{id}` | Retention period expiry |
| **MCP** | Any scheduled tool call | User-specified time |

### Bot Lifecycle Integration (first consumer)

The scheduler's first real consumer is bot-lifecycle's `max_bot_time` enforcement. This is the server-side anti-zombie safety net — kills bots that exceed their maximum lifetime even if the bot process is hung or unresponsive.

**Flow:**
```
POST /bots (meeting-api)
  ├─ Create meeting record (status=requested)
  ├─ Resolve max_bot_time: per-request → user.data.bot_config → default (2h)
  ├─ POST /scheduler/jobs (runtime-api)
  │   execute_at: now + max_bot_time
  │   request: DELETE http://meeting-api:8080/bots/{platform}/{meeting_id}
  │   headers: X-Admin-API-Key (internal)
  │   metadata: {type: "bot_timeout", meeting_id, user_id}
  │   idempotency_key: "bot_timeout_{meeting_id}"
  ├─ Store scheduler_job_id in meeting.data
  └─ Spawn bot container via runtime-api

Bot exits normally (callback → completed/failed)
  └─ DELETE /scheduler/jobs/{job_id} — cancel the timeout job

User stops bot (DELETE /bots)
  └─ DELETE /scheduler/jobs/{job_id} — cancel the timeout job

Timeout fires (bot still alive after max_bot_time)
  └─ Scheduler fires DELETE /bots/{platform}/{meeting_id}
     └─ meeting-api sets status=stopping → signals container → completed (reason=max_bot_time_exceeded)
```

**Why scheduler and not bot-internal timeout?** The bot can hang, lose network, or have bugs. A bot-internal timeout requires the bot to be functioning. The scheduler is completely independent — it fires an HTTP DELETE regardless of bot state. Defense in depth.

See `features/bot-lifecycle/README.md` for the full timeout model.

### Data stages

| Stage | Contents | Produced by | Consumed by |
|-------|----------|-------------|-------------|
| **rendered** | Job execution results (request/response pairs) | Executor | Tests, monitoring |

### Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `SCHEDULER_POLL_INTERVAL` | `5` | Seconds between executor polls |
| `SCHEDULER_REQUEST_TIMEOUT` | `30` | Default HTTP timeout for job execution |
| `SCHEDULER_HISTORY_TTL` | `604800` | History retention in seconds (7 days) |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |

## How

### Current implementation

The scheduler core is implemented and tested in runtime-api:

```bash
# Run unit tests
cd services/runtime-api
python3 -m pytest tests/test_scheduler.py -v
```

### Wiring

The executor is wired into runtime-api main.py:

```python
from runtime_api.scheduler import start_executor, stop_executor
```

### REST API (not yet implemented)

```bash
# Schedule a job
curl -X POST http://localhost:8066/schedule \
  -H "X-API-Key: vxa_bot_..." \
  -d '{
    "execute_at": "2026-03-24T10:00:00Z",
    "request": {"method": "POST", "url": "/bots", "body": {"meeting_url": "..."}},
    "idempotency_key": "my-unique-key"
  }'

# List pending jobs
curl http://localhost:8066/schedule?status=pending

# Cancel a job
curl -X DELETE http://localhost:8066/schedule/job_abc123
```

### Verify

```bash
cd features/scheduler/tests
make env-check    # verify Redis + .env
make test-unit    # runtime-api scheduler unit tests
make test-e2e     # schedule a job, verify execution (needs running services)
make test         # all tests
```

## Roadmap

### Phase 1: Wire executor into runtime-api
- Start executor alongside runtime-api (already wired into runtime-api main.py)
- No REST API yet — jobs scheduled via Python API

### Phase 2: REST API + gateway proxy
- Add `POST/GET/DELETE /schedule` endpoints to runtime-api
- Proxy through api-gateway
- Expose as MCP tool: `schedule_api_call`

### Phase 3: Calendar integration
- Calendar-service uses scheduler to queue bot-join jobs
- Idempotency keys prevent duplicate bots per calendar event
- Callbacks update calendar_events table on success/failure

### Phase 4: Migrate webhook retry
- Replace webhook_retry_worker's Redis list with scheduler sorted set
- Webhook retry becomes just another scheduled job
- Unified monitoring for all scheduled work

### Phase 5: Advanced features
- Job priorities (high-priority jobs execute first when multiple are due)
- Rate limiting (max N concurrent executions)
- Dead letter queue with alerting
- Dashboard UI for job monitoring
- Cron-like recurring jobs
