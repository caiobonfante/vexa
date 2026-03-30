# Scheduler Test Findings

## Gate verdict: PASS (unit + E2E)

## Score: 80

## Test run: 2026-03-25

### Unit tests: 16/16 PASS (unchanged from 2026-03-23)

### E2E tests: PASS (6/6)

Redis is exposed on host port 6389 (`REDIS_URL=redis://localhost:6389`). The "blocked by Redis port" was stale information — port was already mapped in docker-compose.

| Test | Result | Evidence |
|------|--------|----------|
| Schedule job | PASS | `schedule_job()` returns job_id, `ZCARD scheduler:jobs` = 1 |
| Executor fires job | PASS | After 8s executor run, pending = 0, job completed |
| History recorded | PASS | `HGET scheduler:history {job_id}` = `{"status": "completed"}` |
| Idempotency | PASS | Same `idempotency_key` returns same `job_id` |
| Cancellation | PASS | `cancel_job()` removes from queue, pending = 0 |
| External HTTP call | PASS | Job fired POST to httpbin.org/post and got 200 |

**Note:** Original E2E test script (`test-scheduler-e2e.sh`) has a bug — `scheduler:history` is a hash but script uses `lrange` (list op). The core scheduler works correctly; the test script needs a minor fix.

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Job scheduling | 90 | 8 unit tests + E2E pass | 2026-03-25 | — |
| Job cancellation | 90 | 3 unit tests + E2E pass | 2026-03-25 | — |
| Job listing/lookup | 90 | 3 unit tests pass | 2026-03-23 | — |
| Crash recovery | 90 | 1 unit test passes | 2026-03-23 | — |
| Idempotency | 90 | 1 unit test + E2E pass | 2026-03-25 | — |
| Executor fires jobs | 90 | E2E: job fired, completed, history recorded | 2026-03-25 | — |
| Retry on failure | 70 | Unit test passes. E2E not tested (test script bug) | 2026-03-25 | Fix test script, run retry E2E |
| Callbacks | 0 | Not tested | — | E2E with callback receiver |
| REST API | 0 | Not implemented | — | Add endpoints |
| Time precision (<5s) | 80 | Job fired within executor poll interval (~5s) | 2026-03-25 | Measure exact delta |

## Implementation status

| Component | Status |
|-----------|--------|
| `scheduler.py` (core API) | Done, tested |
| `scheduler_worker.py` (executor) | Done, tested E2E |
| `test_scheduler.py` (unit) | 16/16 pass |
| E2E validation | 6/6 pass (inline test) |
| REST endpoints | Not started |
| Wired into meeting-api | Not started |

## Next steps

1. Wire executor into meeting-api startup (background task)
2. Add REST API endpoints (POST/GET/DELETE /schedule)
3. Fix test-scheduler-e2e.sh (lrange → hget for history)
