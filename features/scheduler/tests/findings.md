# Scheduler Test Findings

## Gate verdict: PASS (unit) / BLOCKED (E2E — Redis not exposed to host)

## Test run: 2026-03-23

### Unit tests: 16/16 PASS

All core logic validated with mocked Redis:
- Job creation, validation, idempotency (8 tests)
- Cancellation and history (3 tests)
- Lookup and listing with filters (3 tests)
- Crash recovery — orphan re-queue (1 test)
- ISO timestamp parsing (1 test)

### E2E tests: BLOCKED

Redis port 6379 is not mapped to the host (Docker internal only). E2E tests need either:
1. Expose Redis port in docker-compose (`ports: ["6379:6379"]`)
2. Run tests inside Docker
3. Run a local Redis instance

This is an infrastructure config issue, not a code issue.

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Job scheduling | 90 | 8 unit tests pass | 2026-03-23 | — |
| Job cancellation | 90 | 3 unit tests pass | 2026-03-23 | — |
| Job listing/lookup | 90 | 3 unit tests pass | 2026-03-23 | — |
| Crash recovery | 90 | 1 unit test passes | 2026-03-23 | — |
| Idempotency | 90 | 1 unit test passes | 2026-03-23 | — |
| Executor fires jobs | 0 | Blocked — Redis not on host | — | Expose Redis port, run E2E |
| Retry on failure | 0 | Blocked — Redis not on host | — | Expose Redis port, run E2E |
| Callbacks | 0 | Not tested | — | E2E with callback receiver |
| REST API | 0 | Not implemented | — | Add endpoints |
| Time precision (<5s) | 0 | Not tested | — | E2E timing measurement |

## Implementation status

| Component | Status |
|-----------|--------|
| `scheduler.py` (core API) | Done, tested |
| `scheduler_worker.py` (executor) | Done, not wired |
| `test_scheduler.py` (unit) | 16/16 pass |
| `test-scheduler-e2e.sh` | Written, blocked on Redis access |
| REST endpoints | Not started |
| Wired into bot-manager | Not started |

## Next steps

1. Expose Redis port 6379 in docker-compose for host access
2. Wire executor into bot-manager startup
3. Run E2E tests
4. Add REST API endpoints
