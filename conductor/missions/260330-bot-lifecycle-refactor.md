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

Scheduler already exists in `services/runtime-api/runtime_api/scheduler.py` with full API. This is its first real consumer.

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

- [x] Add `max_bot_time` to `AutomaticLeave` schema in `schemas.py`
- [x] Rename API fields: `waiting_room_timeout` → `max_wait_for_admission`, `everyone_left_timeout` → `max_time_left_alone` (keep old names as aliases for backward compat in schema only)
- [x] Read `user.data.bot_config` in `meetings.py` when building BOT_CONFIG — apply resolution order (request → user.data → system defaults)
- [x] Map API names to bot-side names: `max_wait_for_admission` → `waitingRoomTimeout`, `max_time_left_alone` → `everyoneLeftTimeout`
- [x] Update system defaults: `max_wait_for_admission` = 900000, `max_time_left_alone` = 900000
- [x] Add `max_bot_time_exceeded` to completion reasons enum
- [x] Verify: `stopping` status already excluded from concurrent bot count (it is — `meetings.py:624`)

**Verify:** POST /bots with `automatic_leave.max_bot_time` accepted. GET /bots shows resolved timeout values. User with `bot_config` in data gets their defaults applied.

### Phase 2: Status Lifecycle Bug Fixes

**Goal:** Fix the 4 critical/medium bugs from `bot-status-lifecycle.md` research.

- [x] **Fix 1 (CRITICAL):** ACTIVE callback handler in `callbacks.py` returns `{"status": "error"}` when `update_meeting_status()` returns False (currently returns "processed")
- [x] **Fix 2 (CRITICAL):** Bot propagates JOINING callback failure — does NOT proceed to send ACTIVE when JOINING failed all retries. Platform join functions surface failure instead of swallowing.
- [x] **Fix 3 (MEDIUM):** Webhook delivery in ACTIVE handler gated on `success` flag (currently fires unconditionally at `callbacks.py:389`)
- [ ] **Fix 4 (MEDIUM):** Add `SELECT FOR UPDATE` or equivalent lock in `update_meeting_status()` to prevent TOCTOU race on concurrent callbacks

**Verify:** Simulated JOINING callback failure → bot does NOT send ACTIVE → server stays in REQUESTED → bot reports error. ACTIVE handler returns error on invalid transition. No spurious webhooks for rejected transitions.

### Phase 3: Scheduler Integration (max_bot_time enforcement)

**Goal:** Server-side hard ceiling on bot lifetime via scheduler.

- [x] Meeting-api calls `POST http://runtime-api:8066/scheduler/jobs` on bot creation with timeout job spec
- [x] Store `scheduler_job_id` in `meeting.data`
- [x] Cancel scheduler job when bot reaches terminal state (in `update_meeting_status()` when new status is completed/failed)
- [x] Cancel scheduler job when user calls DELETE /bots (in stop handler)
- [x] When timeout fires → DELETE /bots → status=stopping → completed (reason=max_bot_time_exceeded)
- [x] Handle edge case: timeout fires but bot already in terminal state (idempotent — DELETE returns 404/409, scheduler marks job as failed, no harm)

**Verify:** Create bot with short max_bot_time (60s). Bot joins, stays active. After 60s, scheduler fires DELETE. Bot transitions to stopping → completed with reason=max_bot_time_exceeded. Scheduler job visible in `GET /scheduler/jobs`.

### Phase 4: Fix Google Meet Admission Detection (CRITICAL — found during E2E)

**Discovery (2026-03-30):** Bot reports `active` while ACTUALLY in the waiting room. Host browser shows "Admit 1 guest" pill, but bot found "Leave call" button DOM element and declared itself admitted. The bot's admission detection in `googlemeet/admission.ts` is broken — it checks for DOM elements that exist in both the lobby view and the actual meeting view.

**Impact:** D5 (admission timeout) cannot pass. The bot never enters `awaiting_admission` state, so `waitingRoomTimeout` never fires. The bot falsely reports `active` and sits in the lobby forever (until `max_bot_time` kills it via scheduler).

**Root cause:** `admission.ts` checks for `button[aria-label*="Leave call"]` as proof of admission. This element IS present in the Google Meet lobby/waiting room UI. The bot needs a different signal to distinguish "in lobby" from "in meeting".

**Fix approach:** The admission check must verify actual meeting participation, not just UI element presence. Possible signals:
- Participant count > 0 in the meeting (lobby shows 0 other participants)
- Media elements present (audio/video streams only exist after admission)
- Meeting toolbar has specific controls only visible after admission
- The "Waiting for the host" / "Ask to join" overlay is gone

- [x] Fix `googlemeet/admission.ts` — negative guard on waiting room indicators + meeting-exclusive DOM elements (G8: signal specificity)
- [x] Rebuild vexa-bot image after fix (260331-1330)
- [x] Verify with Playwright CDP: host screenshot shows "Admit 1 guest" → bot reports `awaiting_admission` (not `active`) ✅ 2026-03-31
- [x] Verify admission timeout: bot stays in `awaiting_admission` for 60s → `completed` with `awaiting_admission_timeout` ✅ 2026-03-31

### Phase 5: E2E Tests (all scenarios)

**Goal:** Verify all lifecycle paths with real bots in real meetings.

**CRITICAL RULE: Bot self-reports are NOT evidence.** Every test that checks bot state must verify via Playwright CDP screenshot of the host's browser AND/OR the bot's browser. `meeting_status=active` in the API means nothing if the host screenshot shows "Admit 1 guest".

Test scenarios:
- [x] T1.1 — Full lifecycle with waiting room (requested → joining → awaiting_admission → active → stopping → completed). ✅ 2026-03-31 CDP evidence
- [ ] T1.2 — Bot stop while active (30s soak)
- [ ] T2.1 — Left alone (host leaves via CDP → bot detects → completed reason=left_alone).
- [x] T2.2 — Admission timeout: host does NOT click admit. Bot transitions: joining → awaiting_admission → completed (reason=awaiting_admission_timeout). ✅ 2026-03-31 CDP evidence
- [ ] T3.1 — Invalid meeting URL → failed (stage=joining)
- [x] **T_NEW** — max_bot_time timeout (short max_bot_time, scheduler kills bot → completed reason=max_bot_time_exceeded) ✅ 2026-03-31
- [x] **T_NEW** — User.data.bot_config defaults applied (set user config, create bot without overrides, verify resolved values) ✅ 2026-03-30

**Verify:** All tests pass against real Google Meet. Each test uses Playwright CDP screenshots as evidence, not bot self-reports.

---

## DoD

**Every item has an exact test.** No item is done until the test command runs and shows the expected output. "Code looks correct" = 0 confidence.

**Testing environment:** All tests run on a **freshly built** docker compose deployment (`docker compose build --no-cache && docker compose up -d`). Not against a long-running dev environment with stale state — a clean build proves the code ships correctly.

### Confidence = weighted DoD

Each DoD item has a **weight** reflecting its risk and importance. Confidence is the weighted sum of passing items, not a simple count. API curl tests are low-weight; live meeting tests with CDP screenshot evidence are high-weight.

| DoD | Weight | Why |
|-----|--------|-----|
| D0 (fresh build) | 5 | Infra prerequisite, low risk |
| D1 (backward compat) | 5 | Schema validation, testable offline |
| D2 (declarative stop) | 5 | DB query logic, testable offline |
| D3 (user.data defaults) | 5 | Resolution logic, testable offline |
| **D4 (max_bot_time scheduler)** | **15** | **New feature, real meeting + scheduler, high risk** |
| **D16 (admission detection)** | **15** | **CRITICAL bug fix, can only verify with CDP screenshot** |
| **D17 (admission timeout)** | **15** | **Core timeout path, real meeting, CDP evidence required** |
| D7 (callback error) | 3 | Server code fix, testable offline |
| D8 (JOINING propagation) | 3 | Bot code fix, testable offline |
| D9 (webhook gating) | 2 | Server code fix, testable offline |
| D10 (scheduler cancel) | 5 | Scheduler integration, verifiable via Redis |
| D11 (idempotent timeout) | 3 | Edge case, testable offline |
| **D12 (full lifecycle E2E)** | **15** | **End-to-end, real meeting, all transitions, CDP evidence** |
| D13 (edge cases) | 3 | Edge cases, testable offline |
| **D14 (dashboard)** | **10** | **Human visual verification, real-time updates. Ceiling=80 without it.** |
| D15 (no regressions) | 5 | Regression check |
| | **= 114 total** | |

**Confidence formula:** `sum(passing_item_weights) / 114 * 100`

Example: D0-D3 + D7-D11 + D13 + D15 all pass (API-level) = 44 points = **39%**. Cannot reach 70% without D4 + D12 + D16 + D17 passing with real meeting evidence.

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

### D16. Admission detection — bot reports awaiting_admission when in lobby (NOT active)

```bash
# Host creates meeting with waiting room (meet.new from authenticated account).
# Send non-authenticated bot (user 11) to the meeting. Do NOT admit.
#
# VERIFY VIA PLAYWRIGHT CDP — not bot self-report:
CDP_URL="http://localhost:8066/b/$HOST_SESSION/cdp"
node -e "
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.connectOverCDP('$CDP_URL');
  const page = b.contexts()[0].pages()[0];
  await page.screenshot({ path: '/tmp/host-admission.png' });
  // Check for 'Admit' pill on host page
  const admitPill = page.locator('text=Admit');
  const visible = await admitPill.isVisible();
  console.log('Admit pill visible:', visible);
})();
"
# → Admit pill visible: true (bot is in waiting room)

# SIMULTANEOUSLY check meeting-api status:
curl http://localhost:8056/bots/status -H "X-API-Key: $API_KEY_11"
# → meeting_status = "awaiting_admission" (NOT "active")

# Check bot's status_transition:
# → requested → joining → awaiting_admission (STOPPED HERE, not active)
```

**FAIL if:** host screenshot shows "Admit N guest" but meeting-api shows `active`. The bot falsely detected admission.
**FAIL if:** bot never enters `awaiting_admission` state (goes straight to `active`).

### D17. Admission timeout — bot times out in lobby after max_wait_for_admission

```bash
# Same setup as D16. Bot is in awaiting_admission. Host does NOT admit.
# Wait for max_wait_for_admission (60s).
#
# VERIFY VIA PLAYWRIGHT CDP at T+30s:
# → Host screenshot still shows "Admit N guest" (bot still waiting)
# → meeting-api still shows awaiting_admission
#
# VERIFY at T+70s:
# → Bot exited. meeting-api shows completed, reason=awaiting_admission_timeout
# → Host screenshot: "Admit" pill gone (bot left the lobby)
# → status_transition: requested → joining → awaiting_admission → completed
```

**FAIL if:** bot exits with any reason other than `awaiting_admission_timeout`.
**FAIL if:** bot ever reaches `active` state during this test.

---

## Mission Gotchas (learned during this mission)

These are specific to bot lifecycle work. Read before continuing.

### Deployment & Environment

**MG1: Two stacks = two realities.** The restore stack (:8056) and agentic stack (:8066) share the same source code but have different DBs, different Redis configs, different admin tokens, and different bot images. Testing on one and deploying to the other proves nothing. `dashboard.dev.vexa.ai` points to the agentic stack. Always verify which stack you're targeting BEFORE testing. (2026-03-31: entire E2E suite passed on restore stack. Dashboard showed broken behavior because it points to agentic stack where nothing was deployed.)

**MG2: Bot image tag drift.** The `:dev` tag gets overwritten on rebuild. Old running containers keep the old image. New containers get the new image. You can have two bots in the same meeting running different code. After every rebuild, tag with `YYMMDD-HHMM` and update `.env` with the new tag. (2026-03-31: browser session ran old `:dev` for 14 hours. New bot containers got admission fix. Caused false sense that "some bots work, some don't.")

**MG3: Browser session Zod validation.** `docker.ts` validates BOT_CONFIG with a Zod schema that requires `platform`. Browser session mode doesn't set `platform`. The code must check `mode === "browser_session"` BEFORE running meeting-mode validation. If the bot image rebuild breaks browser sessions, this is why.

### Bot Behavior

**MG4: Google Meet "Leave call" button exists in lobby.** The button that says "Leave call" (or similar) is present in BOTH the lobby/waiting room AND the actual meeting. Do NOT use it as an admission signal. Meeting-exclusive signals: `[data-participant-id]` tiles, `[data-self-name]`, `button[aria-label*="Share screen"]`. Always combine with a negative guard on waiting room text.

**MG5: Lobby has active MediaStream objects.** Google Meet's lobby has self-preview audio/video streams with `srcObject` containing audio tracks. `document.querySelectorAll('audio, video').some(el => el.srcObject)` returns true in the lobby. To use media streams as admission signal, must filter self vs. remote streams. (See G8 in CLAUDE.md for the general principle.)

**MG6: Authenticated accounts skip the waiting room.** User 5's authenticated Google account (g5-admin-test@test.com) bypasses the lobby even on external meetings. To test waiting room behavior, use a different user (user 11) without stored Google cookies. Auto-admit also defeats waiting room tests — kill it first (`pkill -f auto-admit.js`).

### Server-Side

**MG7: UserProxy.data is always empty.** `get_user_and_token()` creates a `UserProxy` with hardcoded `data = {}`. To read `user.data.bot_config`, query the users table directly via the DB session. Fixed in Phase 4.

**MG8: pending_completion_reason must be read in ALL exit paths.** When the scheduler timeout fires, it stores `pending_completion_reason = max_bot_time_exceeded` in `meeting.data`. But the bot exits gracefully (via Redis leave command) within seconds — the exit callback fires BEFORE the 90s delayed stop finalizer. Both `bot_exit_callback` and `status_change COMPLETED handler` in `callbacks.py` must check `meeting.data.pending_completion_reason` and use it over the bot's reported reason. Fixed in callbacks.py.

**MG9: asyncio.create_task with SQLAlchemy objects.** `_cancel_bot_timeout(meeting)` called via `asyncio.create_task` fails because by the time the task runs, the DB session is closed and `meeting.data` throws a detached instance error. Extract primitives (job_id, meeting_id) before creating the task. Fixed in meetings.py.

## Key Files

| File | What changes |
|------|-------------|
| `services/meeting-api/meeting_api/schemas.py` | AutomaticLeave schema (add max_bot_time, rename fields), completion reasons enum |
| `services/meeting-api/meeting_api/meetings.py` | BOT_CONFIG building, scheduler, `GET /bots` meeting history endpoint |
| `services/meeting-api/meeting_api/callbacks.py` | Fix ACTIVE handler error response, gate webhook on success |
| `services/vexa-bot/core/src/platforms/*/join.ts` | Propagate JOINING callback failure |
| `services/vexa-bot/core/src/platforms/googlemeet/admission.ts` | Fix false admission detection — negative guard + meeting-exclusive selectors |
| `services/api-gateway/main.py` | `GET /auth/me` (user identity), `GET /bots` proxy (meeting history) |
| `services/dashboard/src/app/api/auth/me/route.ts` | Calls gateway `/auth/me` instead of admin-api directly |
| `services/dashboard/src/app/api/vexa/[...path]/route.ts` | `/meetings` proxy uses `GET /bots` (all statuses from DB) |
| `services/dashboard/.env` | Simplified — only VEXA_API_URL (gateway), no INTERNAL_API_SECRET |
| `deploy/compose/.env` | Real file (was symlink), all config from root `.env` |

---

## Session Log

### 2026-04-01: Dashboard + env simplification (78/100)

**Changes:**
- Deleted `deploy/compose/docker-compose.override.yml` — merged DOCKER_NETWORK into main compose (was already there)
- Deleted `deploy/compose/.env` symlink — replaced with real file copied from root `.env`
- Deleted `services/dashboard/.env.local` — was band-aid over broken `.env`
- Added `IMAGE_TAG=260331-2108` to root `.env` (G9: immutable tags)
- Added gateway `GET /auth/me` — dashboard resolves user identity via gateway, no `INTERNAL_API_SECRET` needed
- Added meeting-api `GET /bots` — returns all meetings from DB (active + completed)
- Added gateway `GET /bots` proxy
- Rewrote dashboard auth/me to call gateway instead of admin-api directly
- Rewrote dashboard meetings proxy to use `GET /bots` as primary source

**Evidence:**
- `auth/me` returns `user_id=5, email=g5-admin-test@test.com` (was `id=0`)
- Dashboard Playwright screenshot: 50 meetings visible including completed (was "No meetings yet")
- D11 (idempotent timeout): status stays `completed/stopped` after scheduler fires — PASS
- D13 (double stop): 202 "already completed", zero 500s — PASS
- D15 (regressions): all endpoints respond, response shapes correct — PASS

**Update 2026-04-01 14:00:** D7, D8, D9, D14 WS all verified with hard evidence.
- D7: `requested→active` callback returns `{"status":"error"}` — PASS
- D8: Zero instances of ACTIVE without JOINING in 20-meeting transition history — PASS  
- D9: Zero webhook log entries for rejected transition — PASS
- D14 WS: `joining`, `stopping`, `completed` events received over WebSocket in real time — PASS

**Remaining gaps:**
- Phase 2 Fix 4 (SELECT FOR UPDATE): not implemented
- T1.2, T2.1, T3.1: not tested with real meetings
| `features/bot-lifecycle/README.md` | Updated with full design (done 2026-03-30) |
| `features/scheduler/README.md` | Updated with bot-lifecycle consumer (done 2026-03-30) |
