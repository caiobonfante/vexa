# Bot Lifecycle

> **Confidence: 0** — Design updated 2026-03-30 with declarative state model, user-managed timeouts, scheduler integration. No implementation yet.
> **Tested:** Unit tests (mocked) cover individual callbacks and transition rules. Live integration tests cover health/status/create only.
> **Not tested:** Full E2E lifecycle against real meetings, error paths with real bots, declarative stop semantics, scheduler-enforced max_bot_time.

## Why

Every bot follows a lifecycle: requested → joining → awaiting_admission → active → stopping → completed/failed. The state machine is well-defined in `meeting_api/schemas.py` with transition rules, completion reasons, and failure stages. But we have three gaps:

1. **No zombie protection.** A bot with a hung container or lost network can live forever. There's no server-side hard ceiling on bot lifetime.
2. **User intent vs container state.** The concurrent bot limit should respect the user's *decision* to have a bot, not whether the container is still running. When a user stops a bot, that slot should free immediately.
3. **Timeout defaults are hardcoded.** Users can't configure how long their bots wait for admission, stay when alone, or run in total. This should be user-managed with sensible defaults.

## What

### Core Principles

#### A. Declarative User-Defined Bot State

**Database state is the source of truth.** Meeting API manages user intent (I want a bot in this meeting). Runtime API manages container lifecycle (the bot container is running/stopped). These are separate concerns.

- **User's stop action is declarative** — `DELETE /bots` sets `status = stopping` in the database immediately. This is the user's declaration: "I no longer want this bot." The concurrent bot slot frees immediately, even if the container takes 90 seconds to die.
- **Concurrent bot limit counts DB state, not containers** — `max_concurrent_bots` counts meetings with status in `(REQUESTED, JOINING, AWAITING_ADMISSION, ACTIVE)`. Once status moves to `stopping`, the slot is free. Meeting API does not care about container state — it limits users from requesting more bots than allowed.
- **Container state is the runtime API's responsibility** — Runtime API manages spawning, killing, idle cleanup. Meeting API tells it what to do; runtime API figures out how.

#### B. User-Managed Bot Timeouts (Anti-Zombie)

Three timeout parameters prevent zombie bots, all user-configurable with defaults:

| Param | Default | Enforced by | Purpose |
|-------|---------|-------------|---------|
| `max_bot_time` | 7200000 (2h) | **Scheduler** (server-side) | Absolute max lifetime from bot creation. Server kills bot even if it's hung or unresponsive. |
| `max_wait_for_admission` | 900000 (15 min) | **Bot internal** | Bot self-terminates if not admitted to the meeting within this time. |
| `max_time_left_alone` | 900000 (15 min) | **Bot internal** | Bot self-terminates if all other participants leave for this long. |

**Why the enforcement split?**
- `max_bot_time` needs **server-side enforcement** — if the bot hangs, loses network, or has a bug, the scheduler fires a DELETE and the container gets killed regardless. No bot cooperation needed.
- `max_wait_for_admission` and `max_time_left_alone` are conditions only the **bot can detect** (waiting room state, participant count), so the bot enforces them internally and reports completion via callback.

**Zombie protection cascade (defense in depth):**
1. Bot internal timeouts (left_alone, wait_for_admission) — bot self-terminates, sends callback
2. Scheduler max_bot_time — server kills bot after absolute max, no bot cooperation needed
3. Container exit callback — if container dies for any reason, exited callback updates DB to terminal state

#### User-Level Defaults (`user.data.bot_config`)

Users can configure their default timeouts via the admin API. These are stored in `user.data`:

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

**Resolution order:** per-request override → `user.data.bot_config` → system defaults.

Per-request overrides via `automatic_leave` in POST /bots:

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

#### Scheduler Integration for `max_bot_time`

When POST /bots creates a meeting:
1. Resolve `max_bot_time` (request → user.data.bot_config → default 2h)
2. Schedule a timeout job via Runtime API scheduler: `POST /scheduler/jobs` with `execute_at = now + max_bot_time`, targeting `DELETE /bots/{platform}/{meeting_id}`
3. Store `scheduler_job_id` in `meeting.data` for cancellation
4. When bot reaches any terminal state (completed/failed) → cancel the scheduler job
5. When user calls DELETE /bots → cancel the scheduler job (user already stopped it)

See `features/scheduler/README.md` for scheduler capabilities.

### The State Machine

```
requested → joining → awaiting_admission → active → stopping → completed
                              |                |                    \
                              v                v                     → failed
                           (timeout/         (error)
                            rejected)
```

Plus `needs_human_help` escalation from joining/awaiting_admission/active.

### States

| Status | Source | Meaning |
|--------|--------|---------|
| requested | POST /bots | Bot created, container spawning |
| joining | bot callback | Bot connecting to meeting |
| awaiting_admission | bot callback | Bot in waiting room |
| active | bot callback | Bot in meeting, transcribing |
| needs_human_help | bot callback | Unknown blocker, needs VNC intervention |
| stopping | DELETE /bots | User declared stop — slot freed, graceful shutdown in progress |
| completed | bot callback / delayed stop | Bot finished normally |
| failed | bot callback / validation | Something went wrong |

### Completion Reasons (status=completed)

| Reason | Trigger |
|--------|---------|
| stopped | User called DELETE /bots |
| max_bot_time_exceeded | Scheduler killed bot after max lifetime |
| validation_error | Post-bot validation failed |
| awaiting_admission_timeout | Timed out in waiting room (max_wait_for_admission) |
| awaiting_admission_rejected | Host rejected admission |
| left_alone | All other participants left (max_time_left_alone) |
| evicted | Kicked from meeting UI |

### Failure Stages (status=failed)

| Stage | When |
|-------|------|
| requested | Failed during creation (bad URL, no container) |
| joining | Failed while connecting to meeting |
| awaiting_admission | Failed in waiting room |
| active | Failed during meeting |

### Transition Rules

Valid transitions (from `schemas.py`):
- `requested` → joining, failed, completed, stopping
- `joining` → awaiting_admission, active, needs_human_help, failed, completed, stopping
- `awaiting_admission` → active, needs_human_help, failed, completed, stopping
- `needs_human_help` → active, failed, stopping, completed
- `active` → stopping, completed, failed
- `stopping` → completed, failed

Invalid transitions are rejected. Each transition is logged in `meeting.data["status_transition"]` with from/to/timestamp/source/reason.

Note: `JOINING → ACTIVE` (skipping `awaiting_admission`) is VALID when there is no waiting room. Not all meetings have waiting rooms.

### Timeouts

| Param | API field | Bot-side field | Default | Enforced by |
|-------|-----------|----------------|---------|-------------|
| Max bot time | `automatic_leave.max_bot_time` | N/A (server-side) | 7200000 (2h) | Scheduler job → DELETE /bots |
| Max wait for admission | `automatic_leave.max_wait_for_admission` | `automaticLeave.waitingRoomTimeout` | 900000 (15 min) | Bot internal timeout |
| Max time left alone | `automatic_leave.max_time_left_alone` | `automaticLeave.everyoneLeftTimeout` | 900000 (15 min) | Bot internal timeout |
| No one joined | `automatic_leave.no_one_joined_timeout` | `automaticLeave.noOneJoinedTimeout` | 120000 (2 min) | Bot internal timeout |

`BOT_STOP_DELAY_SECONDS` = 90 (env var on meeting-api, controls graceful shutdown delay after DELETE /bots).

**Field mapping:** The API uses descriptive names (`max_wait_for_admission`). The bot-side config uses the legacy names (`waitingRoomTimeout`, `everyoneLeftTimeout`). Meeting-api maps between them when building BOT_CONFIG. The legacy bot-side names are a frozen internal contract — rename only when we touch the bot code.

### Known Status Lifecycle Bugs (to fix in this refactor)

See `conductor/missions/bot-status-lifecycle.md` for full research.

| # | Bug | Severity | Location |
|---|-----|----------|----------|
| 1 | ACTIVE callback handler returns `{"status": "processed"}` on rejected transition — bot thinks it succeeded, dashboard stays stuck | CRITICAL | `callbacks.py:327-398` |
| 2 | Bot swallows JOINING callback failure — proceeds to send ACTIVE, server rejects REQUESTED→ACTIVE silently | CRITICAL | `unified-callback.ts`, platform `join.ts` files |
| 3 | Webhook fires unconditionally even for rejected transitions | MEDIUM | `callbacks.py:389` |
| 4 | No DB lock on status update — TOCTOU race on concurrent callbacks | MEDIUM | `meetings.py:140-196` |

### What Tests Verify

For every scenario:
1. **Status transitions** — GET /bots returns correct status at each stage
2. **Transition history** — `data.status_transition[]` has correct from/to/timestamp/source
3. **Timing** — `start_time` set on ACTIVE, `end_time` set on terminal state
4. **Terminal metadata** — completion_reason OR failure_stage + error_details
5. **Redis events** — `bm:meeting:{id}:status` channel publishes each change
6. **Scheduler job** — max_bot_time timeout job created on bot start, cancelled on bot exit

Verification is via Redis pub/sub + GET /bots response. No webhook HTTP receiver needed.

---

<!-- DESIGN: what we want -->

### Test Scenarios

Tests reuse a single hosted Google Meet created via /host-gmeet-meeting-auto flow (browser_session + gmeet-host-auto.js + auto-admit.js). Host once, send multiple bots.

**IMPORTANT**: Tests use REAL meetings, not fake meeting codes. The only exception is T3.1 (invalid URL) which deliberately uses a fake code to test error handling. T2.2 (admission timeout) uses the REAL meeting with auto-admit stopped — the bot sits in a real waiting room.

#### Tier 1: Happy Path (must have)

**T1.1 — Full lifecycle with waiting room (Google Meet)**
1. Auto-admit running on host session
2. POST /bots with meeting URL → observe: requested → joining → awaiting_admission → active
3. Subscribe to Redis `bm:meeting:{id}:status`, verify events for each transition
4. DELETE /bots → observe: stopping → completed (reason=stopped)
5. Verify all 6 transitions in status_transition array with timestamps

**Speed targets**:
- POST /bots → `awaiting_admission`: **< 10s** (baseline: ~16s — needs optimization)
- POST /bots → `active`: track, optimize later

**T1.2 — Bot stop while active**
Same as T1.1 but let bot run 30s in active before stopping. Verify clean shutdown + all transitions.

#### Tier 2: Completion Reasons (must have)

**T2.1 — Left alone**
1. Bot joins and reaches `active` (with auto-admit)
2. Host leaves the meeting (navigate away via CDP)
3. Bot detects it's alone → `completed` (reason=left_alone)
4. Use short everyone_left_timeout (~30s) via API override

**T2.2 — Admission timeout**
Uses the SAME real hosted meeting — NOT a fake meeting code.
1. Stop auto-admit before this test (`pkill -f auto-admit.js`)
2. Create bot with the REAL meeting URL + short waiting_room_timeout (~60s) via API override
3. Bot joins real meeting, enters real waiting room → `awaiting_admission`
4. Nobody admits it → timeout → `completed` (reason=awaiting_admission_timeout)
5. Restart auto-admit for subsequent tests

#### Tier 3: Error Paths (should have)

**T3.1 — Invalid meeting URL**
POST /bots with fake URL → `failed` (stage=joining) with error_details populated

**T3.2 — Bot eviction**
1. Bot is `active` in meeting
2. Host kicks bot from meeting UI (via CDP)
3. Bot detects removal → `completed` (reason=evicted)

#### Tier 4: Performance (should have)

**T4.1 — Join speed baseline**
10 runs of T1.1, record per-segment timing:
- POST → requested (<1s expected)
- requested → joining (container start)
- joining → awaiting_admission (browser nav + meeting join)
- awaiting_admission → active (auto-admit latency)

Report p50/p90/max. Bot joining should be as fast as possible without breaking.

### How to Host a Meeting (for tests)

```bash
# 1. Get API key + create browser session
API_KEY=$(curl -s -X POST "http://localhost:8056/admin/users/5/tokens?scope=bot" \
  -H "X-Admin-API-Key: changeme" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

curl -s -X POST "http://localhost:8056/bots" \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"mode": "browser_session"}'
# → SESSION_TOKEN from response .data.session_token

# 2. Wait for CDP
CDP_URL="http://localhost:8056/b/$SESSION_TOKEN/cdp"
curl -s -o /dev/null -w "%{http_code}" "$CDP_URL/json/version"

# 3. Create meeting + join as host
cd features/realtime-transcription/scripts && CDP_URL="$CDP_URL" node gmeet-host-auto.js

# 4. Start auto-admit
cd features/realtime-transcription/scripts && nohup node auto-admit.js "$CDP_URL" google_meet > /tmp/auto-admit.log 2>&1 &
```

### Platform Order

1. **Google Meet** — first, proven hosting infra
2. **MS Teams** — second, same auto-admit.js supports it

---

<!-- STATE: what we got -->

### Current State

**No E2E tests implemented yet.** This feature is in requirements collection phase.

Existing coverage (all in `packages/meeting-api/tests/`):
- `test_callbacks.py` — mocked unit tests per callback endpoint
- `test_integration.py` — mocked full flows (create → callback → exit)
- `test_integration_live.py` — live but only health/status/create

### Implementation Prerequisites

1. **Add `max_bot_time` to `automatic_leave` in POST /bots API** — extend MeetingCreate schema with new field:

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

2. **User-level defaults in `user.data.bot_config`** — resolution: per-request → user.data → system defaults.

3. **Scheduler integration** — meeting-api schedules a timeout job on bot creation, cancels on bot exit. Requires meeting-api to call runtime-api scheduler API.

4. **Fix status lifecycle bugs** — the 4 bugs listed above must be fixed as part of this refactor.

5. **New completion reason** — `max_bot_time_exceeded` for scheduler-killed bots.

### Open Questions

- [ ] **needs_human_help**: How to trigger in E2E without real VNC scenario?
- [ ] **Teams**: Meeting creation flow for Teams (later)
- [ ] **Scheduler auth**: How does meeting-api authenticate to runtime-api scheduler? Internal network only, or needs a token?

### Key Files

| File | Role |
|------|------|
| `packages/meeting-api/meeting_api/schemas.py` | State machine, transition rules, MeetingCreate |
| `packages/meeting-api/meeting_api/meetings.py` | Bot CRUD, lifecycle control, timeout config (L713) |
| `packages/meeting-api/meeting_api/callbacks.py` | Callback handlers |
| `packages/meeting-api/meeting_api/config.py` | BOT_STOP_DELAY_SECONDS |
| `services/vexa-bot/core/src/docker.ts` | Bot-side timeout defaults (L22-24) |
| `services/vexa-bot/core/src/platforms/shared/meetingFlow.ts` | Bot-side lifecycle flow |
| `services/vexa-bot/core/src/services/unified-callback.ts` | Bot→API callback logic |
| `features/realtime-transcription/scripts/gmeet-host-auto.js` | Meeting creation |
| `features/realtime-transcription/scripts/auto-admit.js` | Auto-admit for host session |
