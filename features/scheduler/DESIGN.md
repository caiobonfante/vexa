# Scheduler Design

## Problem

Vexa needs to call its own APIs at scheduled times. Primary use case: send a bot to a meeting 1 minute before it starts. But the scheduler should be generic — any "call this API at time T" job.

## Requirements

1. **Schedule API** — accept when + what (HTTP call spec)
2. **Executor** — fire the call at the scheduled time
3. **Bullet-proof** — retries on failure, idempotent, survives restarts
4. **Observable** — know what's scheduled, what fired, what failed

## Architecture

### Two components

```
┌──────────────────┐         ┌──────────────────┐
│  Schedule API    │         │  Executor         │
│  (REST endpoint) │         │  (background loop)│
│                  │         │                   │
│  POST /schedule  │───────▶│  Poll Redis ZSET  │
│  GET /schedule   │  Redis │  Pop due jobs     │
│  DELETE /schedule│  ZSET  │  Fire HTTP call   │
│                  │         │  Retry on failure │
└──────────────────┘         └──────────────────┘
```

### Redis data structure

**Sorted Set** — `scheduler:jobs` keyed by execution timestamp:

```
ZADD scheduler:jobs <execute_at_unix> <job_json>
```

Each job is a self-contained JSON blob:

```json
{
  "job_id": "job_abc123",
  "execute_at": 1774224000,
  "created_at": 1774220400,
  "status": "pending",

  "request": {
    "method": "POST",
    "url": "http://api-gateway:8000/bots",
    "headers": {
      "X-API-Key": "vxa_user_...",
      "Content-Type": "application/json"
    },
    "body": {
      "platform": "google_meet",
      "native_meeting_id": "abc-defg-hij",
      "bot_name": "Calendar Bot"
    }
  },

  "retry": {
    "max_attempts": 3,
    "backoff": [30, 120, 300],
    "attempt": 0
  },

  "metadata": {
    "source": "calendar",
    "calendar_event_id": "evt_123",
    "user_id": 1,
    "meeting_title": "Team Standup"
  },

  "callback": {
    "on_success": "http://calendar-service:8071/internal/job-completed",
    "on_failure": "http://calendar-service:8071/internal/job-failed"
  }
}
```

### Why Sorted Set (not List)

- **Time-ordered** — `ZRANGEBYSCORE scheduler:jobs -inf <now>` gets only due jobs
- **Atomic pop** — `ZPOPMIN` prevents duplicate execution across workers
- **Peek** — `ZRANGE` to see upcoming jobs without removing
- **Efficient** — O(log N) insert, O(1) pop min

### Why not the webhook retry approach (List)?

The webhook retry worker uses `RPUSH`/`LPOP` on a list and checks `next_retry_at` inside the entry. This works but scans ALL entries every poll cycle. A sorted set only returns due items — O(log N) vs O(N).

## Schedule API

### POST /schedule — create a job

```
POST /schedule
{
  "execute_at": "2026-03-23T10:00:00Z",    // ISO 8601 or unix timestamp
  "request": {
    "method": "POST",
    "url": "/bots",                          // relative to API gateway, or absolute
    "headers": {},                           // optional, X-API-Key added automatically
    "body": {}                               // request payload
  },
  "retry": {                                 // optional
    "max_attempts": 3,
    "backoff": [30, 120, 300]
  },
  "metadata": {},                            // optional, caller context
  "callback": {                              // optional, notify on outcome
    "on_success": "http://...",
    "on_failure": "http://..."
  },
  "idempotency_key": "cal_evt_123_bot"      // optional, prevents duplicate scheduling
}

Response: 201
{
  "job_id": "job_abc123",
  "execute_at": "2026-03-23T10:00:00Z",
  "status": "scheduled"
}
```

### GET /schedule — list scheduled jobs

```
GET /schedule?status=pending&source=calendar&limit=20

Response: 200
{
  "jobs": [
    {"job_id": "...", "execute_at": "...", "status": "pending", "metadata": {...}},
    ...
  ]
}
```

### GET /schedule/{job_id} — get job details

```
Response: 200
{
  "job_id": "job_abc123",
  "execute_at": "...",
  "status": "pending|executing|completed|failed|cancelled",
  "request": {...},
  "result": {
    "status_code": 201,
    "response_time_ms": 340,
    "attempts": 1,
    "completed_at": "..."
  }
}
```

### DELETE /schedule/{job_id} — cancel a job

```
Response: 200
{"job_id": "job_abc123", "status": "cancelled"}
```

## Executor

Background loop that runs inside the scheduler service (or inside runtime-api/calendar-service as a task).

```python
async def executor_loop(redis):
    while not stop_event.is_set():
        # Pop all due jobs atomically
        now = time.time()
        due_jobs = await redis.zrangebyscore("scheduler:jobs", "-inf", now)

        for job_data in due_jobs:
            job = json.loads(job_data)
            # Remove from ZSET (atomic — if another worker got it, this returns 0)
            removed = await redis.zrem("scheduler:jobs", job_data)
            if not removed:
                continue  # another worker handled it

            # Move to executing set (track in-flight jobs)
            job["status"] = "executing"
            await redis.hset("scheduler:executing", job["job_id"], json.dumps(job))

            # Fire the HTTP call
            try:
                result = await fire_request(job)
                job["status"] = "completed"
                job["result"] = result
                await notify_callback(job, "on_success")
            except Exception as e:
                attempt = job["retry"]["attempt"] + 1
                max_attempts = job["retry"].get("max_attempts", 3)

                if attempt < max_attempts:
                    # Re-schedule with backoff
                    backoff = job["retry"]["backoff"]
                    delay = backoff[min(attempt - 1, len(backoff) - 1)]
                    job["retry"]["attempt"] = attempt
                    job["status"] = "pending"
                    await redis.zadd("scheduler:jobs", {json.dumps(job): now + delay})
                else:
                    job["status"] = "failed"
                    job["error"] = str(e)
                    await notify_callback(job, "on_failure")

            # Remove from executing set
            await redis.hdel("scheduler:executing", job["job_id"])
            # Store in history
            await redis.hset("scheduler:history", job["job_id"], json.dumps(job))
            await redis.expire("scheduler:history", 86400 * 7)  # 7 day retention

        await asyncio.sleep(5)  # poll every 5 seconds
```

### Reliability guarantees

| Scenario | Handling |
|----------|----------|
| Service restart mid-execution | `scheduler:executing` hash tracks in-flight jobs. On startup, check for orphaned executing jobs and re-queue them. |
| Duplicate execution | `ZREM` returns 0 if job already removed by another worker — skip. |
| API call fails | Retry with exponential backoff per job config. |
| API call hangs | HTTP timeout (30s default). Counts as failure, triggers retry. |
| Redis restart | Jobs in sorted set are persisted (RDB/AOF). In-flight jobs in `scheduler:executing` may be lost — startup recovery re-queues them. |
| Duplicate scheduling | `idempotency_key` prevents duplicate jobs. Check before insert. |
| Clock skew | Jobs execute within POLL_INTERVAL of their target time (~5s precision). |

### Idempotency

```python
async def schedule_job(redis, job):
    key = job.get("idempotency_key")
    if key:
        existing = await redis.get(f"scheduler:idempotency:{key}")
        if existing:
            return json.loads(existing)  # return existing job, don't create duplicate
        await redis.set(f"scheduler:idempotency:{key}", json.dumps(job), ex=86400)
    await redis.zadd("scheduler:jobs", {json.dumps(job): job["execute_at"]})
```

This prevents "send two bots to the same meeting" when a calendar event is synced twice.

## Calendar integration usage

```python
# When calendar sync finds a meeting starting at 10:00:
await schedule_job(redis, {
    "execute_at": meeting_start - timedelta(minutes=1),
    "request": {
        "method": "POST",
        "url": f"{API_GATEWAY_URL}/bots",
        "headers": {"X-API-Key": user_api_token},
        "body": {
            "meeting_url": "https://meet.google.com/abc-defg-hij",
            "bot_name": "Calendar Bot"
        }
    },
    "idempotency_key": f"cal_{event_id}_bot",
    "metadata": {
        "source": "calendar",
        "calendar_event_id": event_id,
        "user_id": user_id,
        "meeting_title": "Team Standup"
    },
    "callback": {
        "on_success": f"{CALENDAR_SERVICE_URL}/internal/bot-scheduled",
        "on_failure": f"{CALENDAR_SERVICE_URL}/internal/bot-schedule-failed"
    }
})
```

## Other use cases

The scheduler is generic — any service can use it:

| Use case | When | What |
|----------|------|------|
| Calendar auto-join | 1min before meeting | `POST /bots` |
| Deferred transcription | Meeting end + 30s | `POST /meetings/{id}/transcribe` |
| Meeting reminder | 5min before | Webhook to user endpoint |
| Recording cleanup | 90 days after | `DELETE /recordings/{id}` |
| Token expiry | Before expiry | Internal notification |

## Implementation plan

### Phase 1: Scheduler in shared-models (like webhook_delivery)

Add to `libs/shared-models/shared_models/`:
- `scheduler.py` — `schedule_job()`, `cancel_job()`, `list_jobs()`
- `scheduler_worker.py` — `start_executor()`, `stop_executor()`, executor loop

Runs inside runtime-api (or calendar-service) as a background task, just like the webhook retry worker.

### Phase 2: REST API

Add endpoints to runtime-api (or a new scheduler service):
- `POST /schedule`
- `GET /schedule`
- `GET /schedule/{job_id}`
- `DELETE /schedule/{job_id}`

### Phase 3: Calendar-service integration

Calendar-service uses the scheduler to queue bot-join jobs when events are synced.
