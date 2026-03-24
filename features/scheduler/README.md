# Scheduler

## Why

Agents shouldn't wait to be asked. The scheduler makes Vexa agents **proactive** — they act on a schedule, chain work after events, and orchestrate multi-step pipelines without human intervention.

**The full pipeline no other platform can do:**

```
Schedule: "0 9 * * 1-5" (weekdays 9am)
  → [T-5min] Spawn browser container, warm up authenticated session
  → [T+0]   Join standup meeting, start transcription
  → [During] Live transcripts stream to dashboard via WebSocket
  → [T+end]  meeting.completed event fires
  → on_success: spawn agent container
       → Agent summarizes transcript, extracts action items
       → Creates Linear tickets for anything tagged "TODO"
       → Posts summary to #engineering Slack channel
  → on_success: spawn worker container
       → Worker sends webhook to CRM with meeting metadata
  → All containers die. Zero cost until tomorrow 9am.
```

No human triggered anything. No Zapier. No glue code. One scheduler, `on_success`/`on_failure` callbacks, container chaining.

**How this compares to other agent scheduling:**

| Platform | Scheduling | Container orchestration | Meeting awareness |
|----------|-----------|------------------------|-------------------|
| **OpenClaw** | "Heartbeats" — agent polls itself | No — single process | No |
| **MindStudio** | Cron-like triggers | No — serverless functions | No |
| **Lindy** | Event + time triggers | No — workflow steps | No |
| **Trigger.dev** | Cron + queues + webhooks | Yes — but generic | No |
| **Vexa Scheduler** | Cron + relative delays + event callbacks | **Yes** — spawns/chains containers | **Yes** — native meeting lifecycle |

Vexa's scheduler doesn't just fire HTTP at time T. It **spawns containers, chains them via callbacks, and reclaims them on completion** — with native understanding of meeting lifecycle events (`meeting.completed`, `bot.joined`, `transcript.ready`).

## What

A generic, bullet-proof job scheduler backed by Redis sorted sets. Two components:

1. **Schedule API** — accepts "when" (timestamp) + "what" (HTTP call spec) + "how" (retry, idempotency, callbacks)
2. **Executor** — polls for due jobs, fires HTTP calls, retries on failure, tracks results

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Producers                             │
│  calendar-service  │  bot-manager  │  admin-api  │ MCP  │
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
| **scheduler.py** | `libs/shared-models/shared_models/scheduler.py` | Core API: `schedule_job()`, `cancel_job()`, `list_jobs()`, `get_job()` |
| **scheduler_worker.py** | `libs/shared-models/shared_models/scheduler_worker.py` | Executor loop: poll, fire, retry, callbacks |
| **REST endpoints** | `services/bot-manager/` (or dedicated service) | HTTP API for external scheduling |
| **test_scheduler.py** | `libs/shared-models/shared_models/test_scheduler.py` | 16 unit tests |

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
    "headers": {"X-API-Key": "vxa_user_..."},
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
| **calendar-integration** | `POST /bots` with meeting URL | 1 min before calendar event |
| **webhooks** | Retry failed webhook delivery | Backoff schedule (1m, 5m, 30m, 2h) |
| **post-meeting-transcription** | `POST /meetings/{id}/transcribe` | Meeting end + 30s |
| **recording-cleanup** | `DELETE /recordings/{id}` | Retention period expiry |
| **MCP** | Any scheduled tool call | User-specified time |

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

The scheduler core is implemented and tested in shared-models:

```bash
# Run unit tests (16/16 pass)
cd libs/shared-models
python3 -m pytest shared_models/test_scheduler.py -v
```

### Not yet wired

The executor is not running in any service yet. To activate:

```python
# In any service startup (bot-manager recommended for Phase 1):
from shared_models.scheduler_worker import start_executor, stop_executor

async def startup():
    redis = await create_redis_client()
    asyncio.create_task(start_executor(redis))

async def shutdown():
    await stop_executor()
```

### REST API (not yet implemented)

```bash
# Schedule a job
curl -X POST http://localhost:8066/schedule \
  -H "X-API-Key: vxa_user_..." \
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
make test-unit    # shared-models unit tests (16 pass)
make test-e2e     # schedule a job, verify execution (needs running services)
make test         # all tests
```

## Roadmap

### Phase 1: Wire executor into bot-manager
- Start executor alongside webhook retry worker
- No REST API yet — jobs scheduled via Python API from within bot-manager

### Phase 2: REST API + gateway proxy
- Add `POST/GET/DELETE /schedule` endpoints to bot-manager
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
