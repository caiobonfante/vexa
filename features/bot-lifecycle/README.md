# Bot Lifecycle

> **Confidence: 0** — Feature scaffolded, no E2E tests implemented yet.
> **Tested:** Unit tests (mocked) cover individual callbacks and transition rules. Live integration tests cover health/status/create only.
> **Not tested:** Full E2E lifecycle against real meetings, error paths with real bots, join speed metrics.

## Why

Every bot follows a lifecycle: requested → joining → awaiting_admission → active → stopping → completed/failed. The state machine is well-defined in `meeting_api/schemas.py` with transition rules, completion reasons, and failure stages. But all tests are mocked — no test actually sends a real bot into a real meeting and watches it walk through the state machine. We've seen issues where mocked tests pass but real bots behave differently (timing, race conditions, platform quirks).

This feature ensures the lifecycle contract is verified end-to-end against real meetings with real bots, and that error paths produce actionable reports.

## What

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
| stopping | DELETE /bots | User requested stop, graceful shutdown |
| completed | bot callback / delayed stop | Bot finished normally |
| failed | bot callback / validation | Something went wrong |

### Completion Reasons (status=completed)

| Reason | Trigger |
|--------|---------|
| stopped | User called DELETE /bots |
| validation_error | Post-bot validation failed |
| awaiting_admission_timeout | Timed out in waiting room |
| awaiting_admission_rejected | Host rejected admission |
| left_alone | All other participants left |
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

### Timeouts

Production defaults (passed via `automatic_leave` in POST /bots):

| Timeout | Default | Purpose |
|---------|---------|---------|
| waiting_room_timeout | 900000 (15 min) | How long bot waits in lobby before giving up |
| everyone_left_timeout | 300000 (5 min) | How long bot stays after all participants leave |
| no_one_joined_timeout | 120000 (2 min) | How long bot waits if nobody joins |

These are API fields with defaults — tests can override with shorter values for speed.

`BOT_STOP_DELAY_SECONDS` = 90 (env var on meeting-api, controls graceful shutdown delay).

### What Tests Verify

For every scenario:
1. **Status transitions** — GET /bots returns correct status at each stage
2. **Transition history** — `data.status_transition[]` has correct from/to/timestamp/source
3. **Timing** — `start_time` set on ACTIVE, `end_time` set on terminal state
4. **Terminal metadata** — completion_reason OR failure_stage + error_details
5. **Redis events** — `bm:meeting:{id}:status` channel publishes each change

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

1. **Add `automatic_leave` to POST /bots API** — optional fields in `MeetingCreate` schema with defaults matching production values. Tests pass shorter timeouts, production gets safe defaults.

```json
POST /bots {
  "platform": "google_meet",
  "native_meeting_id": "abc-defg-hij",
  "automatic_leave": {
    "waiting_room_timeout": 60000,
    "everyone_left_timeout": 30000
  }
}
```

2. **Update production timeout defaults** in `meetings.py:713-716`:
   - waitingRoomTimeout: 300000 → 900000 (15 min)
   - everyoneLeftTimeout: 60000 → 300000 (5 min)

### Open Questions

- [ ] **needs_human_help**: How to trigger in E2E without real VNC scenario?
- [ ] **Teams**: Meeting creation flow for Teams (later)

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
