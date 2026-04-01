# Mission: Bot Lifecycle E2E Tests

Focus: features/bot-lifecycle
Problem: All lifecycle tests are mocked. No test verifies real state transitions or error paths against running services with real meetings.
Target: E2E test suite that creates real bots against real meetings, observes every state transition, and covers error paths.
Stop-when: target met OR 5 iterations
Constraint: Collect requirements first — do NOT implement until constraints are resolved.

---

## Decisions Made

1. **Real meetings, not simulated callbacks.** The whole point is to test the real bot joining a real meeting.
2. **Bot joining must be as fast as possible** — but not at the cost of breaking the lifecycle. Speed is a quality metric.
3. **Platform order**: Google Meet first, then MS Teams.
4. **Meeting hosting**: Use browser_session mode + gmeet-host-auto.js (already proven).
5. **Verification**: Redis pub/sub + GET /bots response. No webhook HTTP receiver needed.
6. **Test isolation**: Reuse one meeting across multiple bot tests. Host once, send multiple bots.
7. **Tests live in the feature**: `features/bot-lifecycle/tests/`

---

## Timeouts

### Production defaults (update in meetings.py)

| Timeout | Current | Target | Where |
|---------|---------|--------|-------|
| waitingRoomTimeout | 300000 (5 min) | **900000 (15 min)** | `meetings.py:714` → bot_config |
| everyoneLeftTimeout | 60000 (1 min) | **300000 (5 min)** | `meetings.py:716` → bot_config |
| noOneJoinedTimeout | 120000 (2 min) | keep | `meetings.py:715` → bot_config |
| BOT_STOP_DELAY_SECONDS | 90 | keep | `config.py:28` env var |

### API fields with defaults (prerequisite)

Add `automatic_leave` as an optional nested object to `MeetingCreate` schema. If omitted, production defaults apply. Tests pass shorter values.

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

`meetings.py` merges caller values over defaults:
```python
defaults = {"waitingRoomTimeout": 900000, "noOneJoinedTimeout": 120000, "everyoneLeftTimeout": 300000}
if req.automatic_leave:
    # override only what caller specified
```

### Test timeout values

Keep test timeouts reasonable — long enough that real bots can complete transitions, short enough tests don't drag:

| Scenario | Timeout | Test value | Why |
|----------|---------|------------|-----|
| T2.2 admission timeout | waiting_room_timeout | 60000 (60s) | Bot needs ~15-20s to reach waiting room, then timeout triggers |
| T2.1 left alone | everyone_left_timeout | 30000 (30s) | Bot is already active, just needs to detect emptiness |
| T1.x happy path | defaults | production defaults | No reason to shorten happy path |

---

## How to Create a Meeting (the host side)

### 1. Get API key + create browser session

```bash
API_KEY=$(curl -s -X POST "http://localhost:8056/admin/users/5/tokens?scope=bot" \
  -H "X-Admin-API-Key: changeme" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

curl -s -X POST "http://localhost:8056/bots" \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"mode": "browser_session"}'
# → SESSION_TOKEN from response .data.session_token
```

### 2. Wait for CDP

```bash
CDP_URL="http://localhost:8056/b/$SESSION_TOKEN/cdp"
# Poll until 200:
curl -s -o /dev/null -w "%{http_code}" "$CDP_URL/json/version"
```

### 3. Create meeting + join as host

```bash
cd features/realtime-transcription/scripts && CDP_URL="$CDP_URL" node gmeet-host-auto.js
# Outputs: MEETING_URL=https://meet.google.com/{code}
#          NATIVE_MEETING_ID={code}
#          JOINED=true
```

### 4. Start auto-admit (so bot gets admitted)

```bash
cd features/realtime-transcription/scripts && nohup node auto-admit.js "$CDP_URL" google_meet > /tmp/auto-admit.log 2>&1 &
```

Host the meeting ONCE, then run all bot tests against it.

---

## State Machine Under Test

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
| joining | bot callback | Bot is connecting to meeting |
| awaiting_admission | bot callback | Bot in waiting room |
| active | bot callback | Bot in meeting, transcribing |
| needs_human_help | bot callback | Unknown blocker, needs VNC intervention |
| stopping | DELETE /bots | User requested stop, graceful shutdown |
| completed | bot callback / delayed stop | Bot finished normally |
| failed | bot callback / validation | Something went wrong |

### Completion Reasons (when status=completed)
- `stopped` — user stopped via API
- `validation_error` — post-bot validation failed
- `awaiting_admission_timeout` — timed out in waiting room
- `awaiting_admission_rejected` — admin rejected
- `left_alone` — all other participants left
- `evicted` — kicked from meeting UI

### Failure Stages (when status=failed)
- `requested` — failed during creation
- `joining` — failed while connecting
- `awaiting_admission` — failed in waiting room
- `active` — failed during meeting

---

## Test Scenarios

All tests reuse a single hosted Google Meet created via /host-gmeet-meeting-auto flow (browser_session + gmeet-host-auto.js + auto-admit.js). Verification is via Redis pub/sub + GET /bots.

**IMPORTANT**: Tests use REAL meetings, not fake meeting codes. The only exception is T3.1 (invalid URL) which deliberately uses a fake code to test error handling. T2.2 (admission timeout) uses the REAL meeting with auto-admit stopped — the bot actually sits in a real waiting room.

### Tier 1: Happy Path (must have)

#### T1.1 — Full lifecycle with waiting room
1. Auto-admit running on host session
2. Create bot via POST /bots with meeting URL
3. Subscribe to Redis `bm:meeting:{id}:status`
4. Poll GET /bots/{platform}/{meeting_id} — observe transitions:
   - `requested` (immediate)
   - `joining` (bot container starts)
   - `awaiting_admission` (bot in waiting room)
   - `active` (auto-admit lets bot in)
5. Stop bot via DELETE /bots/{platform}/{meeting_id}
6. Observe: `stopping` → `completed` (reason=stopped)
7. Verify: status_transition array has all 6 hops with timestamps
8. Verify: Redis received matching events for each transition

**Speed targets**:
- POST /bots → `awaiting_admission`: **< 10s** (currently ~16s — needs optimization)
- POST /bots → `active`: track, optimize later

#### T1.2 — Bot stop while active
Same as T1.1 but let bot run 30s in `active` before stopping. Verify clean shutdown + all transitions.

### Tier 2: Completion Reasons (must have)

#### T2.1 — Left alone
1. Bot joins and reaches `active` (with auto-admit)
2. Host leaves the meeting (navigate away via CDP)
3. Bot detects it's alone → `completed` (reason=left_alone)
4. Use short everyoneLeftTimeout (~30s) for test speed

#### T2.2 — Admission timeout (no auto-admit)
Uses the SAME real hosted meeting — NOT a fake meeting code.
1. Stop auto-admit before this test (`pkill -f auto-admit.js`)
2. Create bot with the REAL meeting URL + short waiting_room_timeout (~60s)
3. Bot joins the real meeting, enters the real waiting room → `awaiting_admission`
4. Nobody admits it → timeout → `completed` (reason=awaiting_admission_timeout)
5. Restart auto-admit for subsequent tests

### Tier 3: Error Paths (should have)

#### T3.1 — Invalid meeting URL
1. POST /bots with `meeting_url=https://meet.google.com/xxx-yyyy-zzz` (fake)
2. Bot should fail during join → `failed` (stage=joining) with error_details

#### T3.2 — Bot eviction
1. Bot is `active` in meeting
2. Host kicks bot from meeting UI (via CDP: find remove button, click)
3. Bot detects removal → `completed` (reason=evicted)

### Tier 4: Timing & Performance

#### T4.1 — Join speed baseline
Run T1.1 ten times, record per-segment timing:
- POST → requested (<1s expected)
- requested → joining (container start)
- joining → awaiting_admission (browser nav + meeting join)
- awaiting_admission → active (auto-admit latency)

Report p50/p90/max for each segment.

---

## What to Verify on Every Test

1. **Status transitions** — GET /bots returns correct status at each stage
2. **Transition history** — `data.status_transition[]` has correct from/to/timestamp/source for every hop
3. **Timing** — `start_time` set when ACTIVE, `end_time` set on terminal state
4. **Terminal metadata** — completion_reason OR failure_stage + error_details present
5. **Redis events** — `bm:meeting:{id}:status` channel publishes each status change

---

## Implementation Prerequisites

### 1. Update production timeouts (meetings.py:713-716)
```python
"automaticLeave": {
    "waitingRoomTimeout": 900000,    # 15 min (was 5 min)
    "noOneJoinedTimeout": 120000,    # 2 min (keep)
    "everyoneLeftTimeout": 300000,   # 5 min (was 1 min)
},
```

### 2. Add timeout override to POST /bots API
Add optional fields to `MeetingCreate` schema so tests can pass shorter values without touching production config. Tests would call:
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

---

## Open Questions (remaining)

### Platform Specifics (for Teams, later)
- [ ] Teams meeting creation flow — browser_session + host script?
- [ ] Teams auto-admit differences?

### Edge Cases (nice to have, decide later)
- [ ] Double-callback idempotency
- [ ] Stop during joining (before awaiting_admission)
- [ ] Callback after container is already gone
- [ ] `needs_human_help` — hard to trigger in E2E without real VNC scenario
- [ ] Concurrent bots in same meeting

---

## Key Files

- `services/meeting-api/meeting_api/schemas.py` — state machine, transition rules, MeetingCreate
- `services/meeting-api/meeting_api/meetings.py` — bot CRUD, lifecycle control, timeout config (line 713)
- `services/meeting-api/meeting_api/callbacks.py` — callback handlers
- `services/meeting-api/meeting_api/config.py` — BOT_STOP_DELAY_SECONDS
- `services/vexa-bot/core/src/docker.ts` — bot-side timeout defaults (line 22-24)
- `services/vexa-bot/core/src/platforms/shared/meetingFlow.ts` — bot-side lifecycle flow
- `services/vexa-bot/core/src/services/unified-callback.ts` — bot→API callback logic
- `features/realtime-transcription/scripts/gmeet-host-auto.js` — meeting creation
- `features/realtime-transcription/scripts/auto-admit.js` — auto-admit for host session
