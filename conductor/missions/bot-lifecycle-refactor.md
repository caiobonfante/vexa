# Mission: Bot Lifecycle Refactor

Focus: features/bot-lifecycle
Problem: No zombie protection, no user-configurable timeouts, declarative state principle not enforced, status callbacks have critical bugs.
Target: Bots have a hard server-side lifetime ceiling, user-managed timeouts, declarative stop semantics, and reliable status transitions.
Stop-when: All DoD items verified against running system with real bots.

---

## Core Principles

### A. Declarative User-Defined Bot State

**Database state is the source of truth.** Meeting API manages user intent ("I want a bot in this meeting"). Runtime API manages container lifecycle ("the container is running/stopped"). These are separate concerns.

- **User's stop action is declarative.** `DELETE /bots` sets `status = stopping` in the database immediately. This is the user's declaration: "I no longer want this bot." The concurrent bot slot frees immediately, even if the container takes 90 seconds to die.
- **Concurrent bot limit counts DB state, not containers.** `max_concurrent_bots` counts meetings with status in `(REQUESTED, JOINING, AWAITING_ADMISSION, ACTIVE)`. Once status moves to `stopping`, the slot is free. Meeting API does not care about container state — it limits users from requesting more bots than allowed.
- **Container state is the runtime API's responsibility.** Runtime API manages spawning, killing, idle cleanup. Meeting API tells it what to do; runtime API figures out how.

### B. User-Managed Bot Timeouts (Anti-Zombie)

Three timeout parameters prevent zombie bots, all user-configurable with defaults:

| Param | Default | Enforced by | Purpose |
|-------|---------|-------------|---------|
| `max_bot_time` | 7200000 (2h) | **Scheduler** (server-side) | Absolute max lifetime from bot creation. Server kills bot even if hung. |
| `max_wait_for_admission` | 900000 (15 min) | **Bot internal** | Bot self-terminates if not admitted within this time. |
| `max_time_left_alone` | 900000 (15 min) | **Bot internal** | Bot self-terminates if all other participants leave for this long. |

**Why the enforcement split?**
- `max_bot_time` needs server-side enforcement — if the bot hangs, loses network, or has a bug, the scheduler fires a DELETE regardless. No bot cooperation needed.
- `max_wait_for_admission` and `max_time_left_alone` are conditions only the bot can detect (waiting room state, participant count), so the bot enforces them internally.

**Zombie protection cascade (defense in depth):**
1. Bot internal timeouts (left_alone, wait_for_admission) — bot self-terminates, sends callback
2. Scheduler max_bot_time — server kills bot after absolute max, no bot cooperation needed
3. Container exit callback — if container dies for any reason, exited callback updates DB to terminal state

### C. User-Level Defaults

Stored in `user.data.bot_config`:

```json
PATCH /admin/users/{id}
{
  "data": {
    "bot_config": {
      "max_bot_time": 7200000,
      "max_wait_for_admission": 900000,
      "max_time_left_alone": 900000
    }
  }
}
```

**Resolution order:** per-request `automatic_leave` → `user.data.bot_config` → system defaults.

Per-request overrides:

```json
POST /bots {
  "platform": "google_meet",
  "native_meeting_id": "abc-defg-hij",
  "automatic_leave": {
    "max_bot_time": 3600000,
    "max_wait_for_admission": 60000,
    "max_time_left_alone": 30000
  }
}
```

### D. Scheduler Integration for max_bot_time

When POST /bots creates a meeting:
1. Resolve `max_bot_time` (request → user.data.bot_config → default 2h)
2. Schedule timeout job: `POST /scheduler/jobs` on runtime-api
   - `execute_at`: now + max_bot_time
   - `request`: `DELETE http://meeting-api:8080/bots/{platform}/{meeting_id}` with internal auth
   - `metadata`: `{type: "bot_timeout", meeting_id, user_id}`
   - `idempotency_key`: `"bot_timeout_{meeting_id}"`
3. Store `scheduler_job_id` in `meeting.data`
4. When bot reaches terminal state (completed/failed) → cancel scheduler job
5. When user calls DELETE /bots → cancel scheduler job

Scheduler already exists in `packages/runtime-api/runtime_api/scheduler.py` with full API. This is its first real consumer.

---

## Frozen Contracts

- Status enum values: `requested`, `joining`, `awaiting_admission`, `active`, `stopping`, `completed`, `failed`, `needs_human_help`
- Redis channel prefix `bm:meeting:{id}:status`
- Callback endpoint paths `/bots/internal/callback/*`
- WebSocket message format `{type: "meeting.status", ...}`
- Bot-side `automaticLeave` field names (`waitingRoomTimeout`, `everyoneLeftTimeout`, `noOneJoinedTimeout`) — frozen internal contract, meeting-api maps API names to these

---

## Sub-Work (prior research)

These missions contain detailed research. Don't duplicate — reference them.

- **`bot-status-lifecycle.md`** — Root cause analysis of status ordering bugs. 10 research sections, 9 identified gaps (G1-G9), 5 recommended fixes. The bug fixes in Phase 2 below come from this research.
- **`bot-lifecycle-e2e.md`** — E2E test scenarios (T1.1-T4.1), meeting hosting setup, test timeout values. The test scenarios in Phase 4 below come from this.

---

## Phases

### Phase 1: Declarative State + User Timeouts (API surface)

**Goal:** API accepts new timeout fields, resolves from user.data, passes to bot.

- [ ] Add `max_bot_time` to `AutomaticLeave` schema in `schemas.py`
- [ ] Rename API fields: `waiting_room_timeout` → `max_wait_for_admission`, `everyone_left_timeout` → `max_time_left_alone` (keep old names as aliases for backward compat in schema only)
- [ ] Read `user.data.bot_config` in `meetings.py` when building BOT_CONFIG — apply resolution order (request → user.data → system defaults)
- [ ] Map API names to bot-side names: `max_wait_for_admission` → `waitingRoomTimeout`, `max_time_left_alone` → `everyoneLeftTimeout`
- [ ] Update system defaults: `max_wait_for_admission` = 900000, `max_time_left_alone` = 900000
- [ ] Add `max_bot_time_exceeded` to completion reasons enum
- [ ] Verify: `stopping` status already excluded from concurrent bot count (it is — `meetings.py:624`)

**Verify:** POST /bots with `automatic_leave.max_bot_time` accepted. GET /bots shows resolved timeout values. User with `bot_config` in data gets their defaults applied.

### Phase 2: Status Lifecycle Bug Fixes

**Goal:** Fix the 4 critical/medium bugs from `bot-status-lifecycle.md` research.

- [ ] **Fix 1 (CRITICAL):** ACTIVE callback handler in `callbacks.py` returns `{"status": "error"}` when `update_meeting_status()` returns False (currently returns "processed")
- [ ] **Fix 2 (CRITICAL):** Bot propagates JOINING callback failure — does NOT proceed to send ACTIVE when JOINING failed all retries. Platform join functions surface failure instead of swallowing.
- [ ] **Fix 3 (MEDIUM):** Webhook delivery in ACTIVE handler gated on `success` flag (currently fires unconditionally at `callbacks.py:389`)
- [ ] **Fix 4 (MEDIUM):** Add `SELECT FOR UPDATE` or equivalent lock in `update_meeting_status()` to prevent TOCTOU race on concurrent callbacks

**Verify:** Simulated JOINING callback failure → bot does NOT send ACTIVE → server stays in REQUESTED → bot reports error. ACTIVE handler returns error on invalid transition. No spurious webhooks for rejected transitions.

### Phase 3: Scheduler Integration (max_bot_time enforcement)

**Goal:** Server-side hard ceiling on bot lifetime via scheduler.

- [ ] Meeting-api calls `POST http://runtime-api:8066/scheduler/jobs` on bot creation with timeout job spec
- [ ] Store `scheduler_job_id` in `meeting.data`
- [ ] Cancel scheduler job when bot reaches terminal state (in `update_meeting_status()` when new status is completed/failed)
- [ ] Cancel scheduler job when user calls DELETE /bots (in stop handler)
- [ ] When timeout fires → DELETE /bots → status=stopping → completed (reason=max_bot_time_exceeded)
- [ ] Handle edge case: timeout fires but bot already in terminal state (idempotent — DELETE returns 404/409, scheduler marks job as failed, no harm)

**Verify:** Create bot with short max_bot_time (60s). Bot joins, stays active. After 60s, scheduler fires DELETE. Bot transitions to stopping → completed with reason=max_bot_time_exceeded. Scheduler job visible in `GET /scheduler/jobs`.

### Phase 4: E2E Tests

**Goal:** Verify all lifecycle paths with real bots in real meetings.

Test scenarios from `bot-lifecycle-e2e.md`:
- [ ] T1.1 — Full lifecycle with waiting room (requested → joining → awaiting_admission → active → stopping → completed)
- [ ] T1.2 — Bot stop while active (30s soak)
- [ ] T2.1 — Left alone (host leaves, bot detects → completed reason=left_alone)
- [ ] T2.2 — Admission timeout (no auto-admit, bot times out → completed reason=awaiting_admission_timeout)
- [ ] T3.1 — Invalid meeting URL → failed (stage=joining)
- [ ] **T_NEW** — max_bot_time timeout (short max_bot_time, scheduler kills bot → completed reason=max_bot_time_exceeded)
- [ ] **T_NEW** — User.data.bot_config defaults applied (set user config, create bot without overrides, verify resolved values)

**Verify:** All tests pass against real Google Meet. Each test verifies status transitions, transition history, timing, terminal metadata, and scheduler job lifecycle.

---

## DoD

**Every item has an exact test.** No item is done until the test command runs and shows the expected output. "Code looks correct" = 0 confidence.

**Testing environment:** All tests run on a **freshly built** docker compose deployment (`docker compose build --no-cache && docker compose up -d`). Not against a long-running dev environment with stale state — a clean build proves the code ships correctly.

---

### D0. Fresh build — all affected services start and respond

```bash
# Clean build from scratch
docker compose build --no-cache
docker compose up -d

# Wait for services to be healthy, then verify every affected endpoint responds:
curl -s http://localhost:8056/health          # gateway
curl -s http://localhost:8080/health          # meeting-api
curl -s http://localhost:8066/health          # runtime-api (scheduler lives here)

# Verify scheduler executor is running (log line on startup)
docker logs vexa-runtime-api 2>&1 | grep -i "scheduler.*executor\|executor.*start"

# Verify all bot API endpoints respond (not 502/503):
API_KEY=$(curl -s -X POST "http://localhost:8056/admin/users/5/tokens?scope=bot" \
  -H "X-Admin-API-Key: changeme" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
curl -s -o /dev/null -w "%{http_code}" http://localhost:8056/bots -H "X-API-Key: $API_KEY"
# → 200 (empty list, not 502)
curl -s -o /dev/null -w "%{http_code}" http://localhost:8066/scheduler/jobs
# → 200
```

**FAIL if:** any service doesn't start, any endpoint returns 502/503, scheduler executor not running.

### D1. API backward compatibility — old field names still work

```bash
# Old API format (waiting_room_timeout, everyone_left_timeout) must still be accepted
curl -s -X POST http://localhost:8056/bots -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"platform":"google_meet","native_meeting_id":"compat-test","automatic_leave":{"waiting_room_timeout":60000,"everyone_left_timeout":30000}}'
# → 200 (NOT 422 validation error)

# New API format (max_wait_for_admission, max_time_left_alone) also works
curl -s -X POST http://localhost:8056/bots -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"platform":"google_meet","native_meeting_id":"compat-test-2","automatic_leave":{"max_wait_for_admission":60000,"max_time_left_alone":30000}}'
# → 200

# No automatic_leave at all — system defaults apply
curl -s -X POST http://localhost:8056/bots -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"platform":"google_meet","native_meeting_id":"compat-test-3"}'
# → 200

# GET /bots, DELETE /bots, callback endpoints — all existing contract unchanged
curl -s http://localhost:8056/bots -H "X-API-Key: $API_KEY" | jq 'length'
# → returns list (schema unchanged)
```

**FAIL if:** old field names return 422. FAIL if: any existing API contract broken (response shape, status codes, field names in responses).

### D2. Declarative stop frees slot immediately

```bash
# Setup: user 5 with max_concurrent_bots = 1
# 1. Create bot
curl -X POST http://localhost:8056/bots -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"platform":"google_meet","native_meeting_id":"real-meeting-code"}'
# → 200, status=requested

# 2. Stop bot
curl -X DELETE http://localhost:8056/bots/google_meet/real-meeting-code -H "X-API-Key: $API_KEY"
# → 200, status=stopping

# 3. Immediately create another bot (within the limit of 1)
curl -X POST http://localhost:8056/bots -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"platform":"google_meet","native_meeting_id":"different-meeting-code"}'
# → 200 (NOT 403). Slot freed because first bot is in "stopping", not counted.
```

**FAIL if:** step 3 returns 403 "concurrent bot limit reached".

### D3. User.data.bot_config defaults applied

```bash
# Set user-level defaults
curl -X PATCH http://localhost:8056/admin/users/5 \
  -H "X-Admin-API-Key: changeme" -H "Content-Type: application/json" \
  -d '{"data":{"bot_config":{"max_bot_time":3600000,"max_wait_for_admission":600000,"max_time_left_alone":600000}}}'

# Create bot WITHOUT automatic_leave override
curl -X POST http://localhost:8056/bots -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"platform":"google_meet","native_meeting_id":"defaults-test"}'

# Verify resolved timeouts come from user.data
curl http://localhost:8056/bots/google_meet/defaults-test -H "X-API-Key: $API_KEY" | jq '.data'
# → resolved_timeouts.max_bot_time == 3600000 (from user.data, not system default 7200000)
# → resolved_timeouts.max_wait_for_admission == 600000 (from user.data)

# Create with per-request override — per-request wins
curl -X POST http://localhost:8056/bots -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"platform":"google_meet","native_meeting_id":"override-test","automatic_leave":{"max_bot_time":1800000}}'
# → resolved_timeouts.max_bot_time == 1800000 (per-request wins)
# → resolved_timeouts.max_wait_for_admission == 600000 (user.data, no per-request override for this field)
```

**FAIL if:** resolved timeouts don't follow resolution order (per-request > user.data > system default).

### D4. max_bot_time — scheduler kills bot after lifetime (real meeting)

```bash
# Host real Google Meet (via /host-gmeet-meeting-auto). Auto-admit running.
# Create bot with 60s max_bot_time
curl -X POST http://localhost:8056/bots -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"platform":"google_meet","native_meeting_id":"'$MEETING_ID'","automatic_leave":{"max_bot_time":60000}}'

# Verify scheduler job created
curl http://localhost:8066/scheduler/jobs | jq '.[] | select(.metadata.type=="bot_timeout")'
# → job exists, execute_at ~ now+60s, request.method=DELETE

# Wait for bot to reach active (should be <20s)
# Then wait for timeout to fire (~60s from creation)
# Poll:
curl http://localhost:8056/bots/google_meet/$MEETING_ID -H "X-API-Key: $API_KEY" | jq '.status,.data.completion_reason'
# → "completed", "max_bot_time_exceeded"

# Verify scheduler job completed (not still pending)
curl http://localhost:8066/scheduler/jobs?status=completed | jq 'length'
# → ≥ 1
```

**FAIL if:** bot stays active after 60s. FAIL if: completion_reason is not "max_bot_time_exceeded". FAIL if: no scheduler job was created. FAIL if: bot container still running after timeout.

### D5. max_wait_for_admission — bot self-terminates in waiting room (real meeting)

```bash
# Stop auto-admit: pkill -f auto-admit.js
# Create bot with short admission timeout against REAL meeting
curl -X POST http://localhost:8056/bots -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"platform":"google_meet","native_meeting_id":"'$MEETING_ID'","automatic_leave":{"max_wait_for_admission":60000}}'

# Poll until terminal:
curl http://localhost:8056/bots/google_meet/$MEETING_ID -H "X-API-Key: $API_KEY" \
  | jq '.status,.data.completion_reason'
# → "completed", "awaiting_admission_timeout"

# Verify transition chain
curl http://localhost:8056/bots/google_meet/$MEETING_ID -H "X-API-Key: $API_KEY" \
  | jq '.data.status_transition[] | "\(.from) → \(.to)"'
# → requested → joining → awaiting_admission → completed

# Scheduler timeout job cancelled (bot exited before max_bot_time)
curl http://localhost:8066/scheduler/jobs?status=cancelled | jq '.[] | select(.metadata.type=="bot_timeout")'
# → exists

# Restart auto-admit for subsequent tests
```

**FAIL if:** bot stays in awaiting_admission past 60s. FAIL if: reason is not "awaiting_admission_timeout". FAIL if: scheduler job not cancelled.

### D6. max_time_left_alone — bot self-terminates when alone (real meeting)

```bash
# Auto-admit running. Create bot with short left-alone timeout.
curl -X POST http://localhost:8056/bots -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"platform":"google_meet","native_meeting_id":"'$MEETING_ID'","automatic_leave":{"max_time_left_alone":30000}}'

# Wait for bot to reach active.
# Host leaves meeting (navigate away via CDP or close tab).
# Poll:
curl http://localhost:8056/bots/google_meet/$MEETING_ID -H "X-API-Key: $API_KEY" \
  | jq '.status,.data.completion_reason'
# → "completed", "left_alone"
```

**FAIL if:** bot stays active after everyone leaves for 30s. FAIL if: reason is not "left_alone".

### D7. Status lifecycle — ACTIVE callback returns error on invalid transition

```bash
# Simulate: send ACTIVE callback for a meeting still in REQUESTED state
curl -X POST http://localhost:8080/bots/internal/callback/status_change \
  -H "Content-Type: application/json" \
  -d '{"connection_id":"<session_uid_of_requested_meeting>","status":"active"}'
# → {"status": "error", "detail": "Invalid transition: requested → active"}
# NOT: {"status": "processed"}
```

**FAIL if:** response is `{"status": "processed"}` when transition is invalid.

### D8. Status lifecycle — bot does not send ACTIVE after JOINING failure

```bash
# Block callback endpoint temporarily (e.g., iptables, or stop meeting-api briefly during join)
# Create bot against real meeting
# After JOINING fails all 3 retries, bot should NOT proceed to send ACTIVE.
# Check meeting-api logs:
docker logs vexa-meeting-api 2>&1 | grep "Invalid transition.*requested.*active"
# → ZERO matches (bot didn't try to skip JOINING)
```

**FAIL if:** meeting-api logs show rejected `requested → active` attempt.

### D9. Status lifecycle — webhook gated on success

```bash
# Set up webhook URL on user. Send invalid transition callback (same as D7).
# Check meeting-api logs for webhook delivery:
docker logs vexa-meeting-api 2>&1 | grep "webhook"
# → NO webhook sent for rejected transition
```

**FAIL if:** webhook fires for a transition that was rejected by the state machine.

### D10. Scheduler job cancelled on normal bot exit

```bash
# Create bot with default max_bot_time (2h), real meeting, auto-admit
curl -X POST http://localhost:8056/bots -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"platform":"google_meet","native_meeting_id":"'$MEETING_ID'"}'

# Verify timeout job exists
curl http://localhost:8066/scheduler/jobs | jq '.[] | select(.metadata.type=="bot_timeout")'
# → exists, status=pending

# Stop bot
curl -X DELETE http://localhost:8056/bots/google_meet/$MEETING_ID -H "X-API-Key: $API_KEY"

# Verify timeout job cancelled
curl http://localhost:8066/scheduler/jobs | jq '.[] | select(.metadata.type=="bot_timeout")'
# → empty (moved to history)
curl http://localhost:8066/scheduler/jobs?status=cancelled | jq '.[] | select(.metadata.type=="bot_timeout")'
# → exists
```

**FAIL if:** scheduler job still pending after bot reached terminal state.

### D11. Timeout fires after bot already completed — idempotent, no crash

```bash
# Create bot with 30s max_bot_time. Stop bot at 15s. Wait for timeout at 30s.
# Bot stays completed, reason=stopped (user stop preserved, not overwritten)
curl http://localhost:8056/bots/google_meet/$MEETING_ID -H "X-API-Key: $API_KEY" \
  | jq '.status,.data.completion_reason'
# → "completed", "stopped"

# No errors in meeting-api logs
docker logs vexa-meeting-api 2>&1 | tail -20
# → no 500, no unhandled exception
```

**FAIL if:** bot status changes to max_bot_time_exceeded. FAIL if: any service logs errors or crashes.

### D12. Full lifecycle E2E — all transitions visible (real meeting)

```bash
# Host real Google Meet with auto-admit.
# Create bot. Poll GET /bots every 2s, record every status seen:
#   requested → joining → awaiting_admission → active
# Stop bot:
#   stopping → completed (reason=stopped)

# Verify complete transition history:
curl http://localhost:8056/bots/google_meet/$MEETING_ID -H "X-API-Key: $API_KEY" \
  | jq '.data.status_transition[] | "\(.from) → \(.to) at \(.timestamp)"'
# → 6 transitions, all with timestamps, all in order, no gaps

# Verify timing:
# → start_time set (when ACTIVE), end_time set (when completed)
# → POST /bots → awaiting_admission: track (target < 10s)

# Scheduler timeout job created and then cancelled on stop
```

**FAIL if:** any transition missing. FAIL if: transitions out of order. FAIL if: start_time/end_time not set. FAIL if: scheduler job still pending.

### D13. Edge cases — double stop, stop during joining, concurrent callbacks

```bash
# Double stop: DELETE /bots twice in quick succession
curl -X DELETE http://localhost:8056/bots/google_meet/$MEETING_ID -H "X-API-Key: $API_KEY"
curl -X DELETE http://localhost:8056/bots/google_meet/$MEETING_ID -H "X-API-Key: $API_KEY"
# → second call returns 404 or 409 (already stopping/completed), NOT 500

# Stop during joining: create bot, immediately stop before it reaches active
curl -X POST http://localhost:8056/bots -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"platform":"google_meet","native_meeting_id":"'$MEETING_ID'"}'
sleep 2
curl -X DELETE http://localhost:8056/bots/google_meet/$MEETING_ID -H "X-API-Key: $API_KEY"
# → status=stopping → eventually completed (reason=stopped). No stuck state.

# No 500s in any service logs
docker logs vexa-meeting-api 2>&1 | grep -c "500\|Traceback\|unhandled"
# → 0
docker logs vexa-runtime-api 2>&1 | grep -c "500\|Traceback\|unhandled"
# → 0
```

**FAIL if:** double stop returns 500. FAIL if: early stop leaves bot in non-terminal state. FAIL if: any unhandled exceptions in logs.

### D14. Dashboard — human verifies bot lifecycle is visible

```
Human opens dashboard at https://gateway.dev.vexa.ai (or localhost:8056).
1. Create a bot via API. Dashboard shows bot card with status "Requested".
2. Bot progresses: Joining → Awaiting Admission → Active. Each step visible in real time.
3. Stop bot via API. Dashboard shows "Stopping" → "Completed".
4. Status history tooltip shows all transitions with timestamps.
5. If bot times out (max_bot_time), dashboard shows "Completed" with reason visible.

Human confirms: "I can see the full lifecycle on the dashboard."
```

**FAIL if:** dashboard shows any transition gap (e.g., jumps from Requested to Active). FAIL if: dashboard doesn't update in real time. FAIL if: completion reason not visible.

### D15. No regressions — existing bot operations unaffected

```bash
# After fresh build, run the existing happy path that worked before this refactor:
# 1. Create bot with old API format (no automatic_leave)
# 2. Bot joins real meeting, reaches active
# 3. Stop bot, reaches completed
# 4. All existing fields in response (status, data, start_time, end_time, platform, etc.) unchanged
# 5. Webhook delivery works for successful transitions (if configured)
# 6. Redis pub/sub publishes status changes on bm:meeting:{id}:status

# Compare response schema before and after refactor — no breaking changes
```

**FAIL if:** any existing integration breaks. FAIL if: response fields removed or renamed. FAIL if: Redis channel format changed.

---

## Key Files

| File | What changes |
|------|-------------|
| `packages/meeting-api/meeting_api/schemas.py` | AutomaticLeave schema (add max_bot_time, rename fields), completion reasons enum |
| `packages/meeting-api/meeting_api/meetings.py` | BOT_CONFIG building (resolution order, user.data.bot_config), scheduler job creation/cancellation |
| `packages/meeting-api/meeting_api/callbacks.py` | Fix ACTIVE handler error response, gate webhook on success |
| `services/vexa-bot/core/src/services/unified-callback.ts` | (Read-only for Phase 2 research — bot-side fix is in join.ts files) |
| `services/vexa-bot/core/src/platforms/*/join.ts` | Propagate JOINING callback failure |
| `packages/runtime-api/runtime_api/scheduler.py` | Already implemented — first real consumer |
| `packages/runtime-api/runtime_api/scheduler_api.py` | Already implemented — REST endpoints |
| `features/bot-lifecycle/README.md` | Updated with full design (done 2026-03-30) |
| `features/scheduler/README.md` | Updated with bot-lifecycle consumer (done 2026-03-30) |
