# Mission

Focus: Bot status lifecycle ordering — statuses skip or arrive out of order
Problem: Bot status on dashboard jumps directly to "active" instead of progressing through requested → joining → awaiting_admission → active. Intermediate states are silently dropped.
Target: Every status transition is visible on the dashboard in correct order, with no silent drops
Stop-when: root causes identified, all related gaps cataloged, fix design validated, DoD defined

## Symptom

Bot appears as "active" immediately after creation. The dashboard never shows "requested", "joining", or "awaiting_admission" states. Users can't tell if a bot is still connecting or already in the meeting.

## Known Root Cause (from initial research)

Three interacting problems:

### 1. Fire-and-forget callbacks
Bot sends status callbacks (`joining`, `awaiting_admission`, `active`) as separate HTTP POSTs without waiting for acknowledgment. No ordering guarantee. (`services/vexa-bot/core/src/services/unified-callback.ts:42`)

### 2. Silent rejection of out-of-order transitions
Meeting-api validates status transitions via `is_valid_status_transition()` (`meetings.py:136-138`). Invalid transitions silently return False — no status update, no Redis publish, no error to the bot. If `active` arrives before `joining` is processed, the transition may be rejected or create an invalid jump.

### 3. Client-side timing hacks
Teams bot adds `setTimeout(1000)` to avoid race conditions (`msteams/admission.ts:128-131`). This is fragile — depends on network latency, server load, etc. Google Meet and Zoom have similar timing assumptions.

## Research Needed

1. **State machine definition** — where is `is_valid_status_transition()` defined? What transitions are valid? Is the state machine documented anywhere?
2. **Callback dispatch per platform** — exactly when does each platform (Google Meet, Teams, Zoom) send each callback? Are any skipped intentionally?
3. **Teams immediate admission path** — `msteams/admission.ts:95-99` intentionally skips `awaiting_admission`. Is this correct? What does the dashboard show?
4. **Callback error handling** — what happens when a callback HTTP POST fails? Does the bot retry? Does it proceed anyway?
5. **WebSocket publish timing** — does `publish_meeting_status_change()` fire for every successful transition, or can publishes be lost?
6. **Dashboard rendering** — does the dashboard interpolate missing states or only show what WebSocket delivers? If it only shows WebSocket events, missed intermediates are invisible.
7. **GET /bots/status vs WebSocket** — does the dashboard ever poll status, or is it purely WebSocket-driven? If polling, does it miss fast transitions?
8. **Unified callback endpoint** — `unified-callback.ts` sends ALL status changes to `/bots/internal/callback/status_change`. Does this endpoint handle all states the same way? Or does it have special cases?
9. **Logging/metrics** — are silent transition rejections logged? Can we tell how often this happens from existing logs?
10. **Related gaps in READMEs** — do any docs describe the expected lifecycle incorrectly?

## Frozen Contracts

- Status enum values: `requested`, `joining`, `awaiting_admission`, `active`, `stopping`, `completed`, `failed`, `needs_human_help`
- Redis channel `bm:meeting:{id}:status` — frozen prefix
- Callback endpoint paths `/bots/internal/callback/*` — internal contract
- WebSocket message format `{type: "meeting.status", ...}` — dashboard contract

## Research Findings (v2 — refined 2026-03-30)

**Key clarification:** Skipping `awaiting_admission` is LEGITIMATE when there is no waiting room. `JOINING → ACTIVE` is valid and correct. The bug is specifically about `JOINING` itself being skipped (REQUESTED → ACTIVE) or intermediate states being invisible on the dashboard.

### 1. Complete State Machine (from `services/meeting-api/meeting_api/schemas.py:82-128`)

```
REQUESTED ──→ JOINING ──→ AWAITING_ADMISSION ──→ ACTIVE ──→ STOPPING ──→ COMPLETED
   │             │               │                  │           │
   │             │               │                  │           └──→ FAILED
   │             │               │                  │
   │             │               │                  └──→ COMPLETED
   │             │               │                  └──→ FAILED
   │             │               │
   │             │               └──→ NEEDS_HUMAN_HELP ──→ ACTIVE
   │             │               │                       └──→ FAILED
   │             │               │                       └──→ STOPPING
   │             │               │                       └──→ COMPLETED
   │             │               └──→ FAILED
   │             │               └──→ COMPLETED
   │             │               └──→ STOPPING
   │             │
   │             └──→ ACTIVE (direct — no waiting room, LEGITIMATE)
   │             └──→ NEEDS_HUMAN_HELP
   │             └──→ FAILED
   │             └──→ COMPLETED
   │             └──→ STOPPING
   │
   └──→ FAILED
   └──→ COMPLETED
   └──→ STOPPING
```

**Important:** `JOINING → ACTIVE` (skipping `awaiting_admission`) is VALID and correct. Not all meetings have waiting rooms. The state machine correctly allows this.

**Key finding:** `REQUESTED → ACTIVE` is NOT valid. The state machine requires `REQUESTED → JOINING` before anything else. The ACTIVE handler at `callbacks.py:328` lets `REQUESTED` through its pre-check but then `update_meeting_status()` calls `is_valid_status_transition(REQUESTED, ACTIVE)` → returns False. The transition is silently rejected, BUT the handler still returns `{"status": "processed"}` (line 398) — so the bot thinks it succeeded.

**Docstring gap:** The docstring in `schemas.py:37-40` shows only the happy path, omitting `NEEDS_HUMAN_HELP`, `JOINING → ACTIVE`, and various failure transitions.

### 2. Callback Dispatch Per Platform

#### Bot-side callback wrappers (`services/vexa-bot/core/src/utils.ts`)
- `callJoiningCallback()` → `callStatusChangeCallback(botConfig, "joining")`
- `callAwaitingAdmissionCallback()` → `callStatusChangeCallback(botConfig, "awaiting_admission")`
- `callStartupCallback()` → `callStatusChangeCallback(botConfig, "active")`

All three are async and `await`ed. `callStatusChangeCallback()` (`unified-callback.ts:42-138`) has:
- 3 retries with exponential backoff (1s, 2s, 4s)
- 5-second HTTP timeout per attempt
- Returns `void` — caller doesn't know if server accepted/rejected the transition

#### Google Meet (`platforms/googlemeet/join.ts` + `admission.ts`)
1. **join.ts:26** → `await callJoiningCallback(botConfig)` — BEFORE clicking "Ask to join"
2. **admission.ts:104** → `await callAwaitingAdmissionCallback(botConfig)` — when immediately admitted (NO waiting room)
3. **admission.ts:131** → `await callAwaitingAdmissionCallback(botConfig)` — when waiting room detected
4. **admission.ts:224** → `await callAwaitingAdmissionCallback(botConfig)` — when waiting room appears during polling
5. **meetingFlow.ts:135** → `await callStartupCallback(botConfig)` — after admission confirmed

**Timing:** joining → (immediate or ~2-5s) → awaiting_admission → (human admits) → active
**Gap:** When immediately admitted, both `awaiting_admission` AND `active` are sent within ~1 second. The 1-second delay at `meetingFlow.ts:131` is the only guard.

#### Microsoft Teams (`platforms/msteams/join.ts` + `admission.ts`)
1. **join.ts:274** → `await callJoiningCallback(botConfig)` — after navigation
2. **admission.ts:99** → SKIPS `awaiting_admission` when immediately admitted (explicit comment: "CRITICAL FIX: skip awaiting_admission to avoid race condition")
3. **admission.ts:129-136** → 1-second delay + `await callAwaitingAdmissionCallback(botConfig)` when in waiting room
4. **admission.ts:288-291** → `await callAwaitingAdmissionCallback(botConfig)` when lobby detected during polling
5. **meetingFlow.ts:135** → `await callStartupCallback(botConfig)`

**Correct behavior:** Teams skips `awaiting_admission` for immediate admission (line 96-99) — `JOINING → ACTIVE` is a valid and expected path when there is no waiting room.

#### Zoom Web (`platforms/zoom/web/join.ts` + `admission.ts`)
1. **join.ts:83** → `await callJoiningCallback(botConfig)` — after page load
2. **admission.ts:86** → `await callAwaitingAdmissionCallback(botConfig)` — when in waiting room
3. **admission.ts:77-79** → Returns `true` immediately if admitted — NO `awaiting_admission` callback
4. **meetingFlow.ts:135** → `await callStartupCallback(botConfig)`

**Correct behavior:** Zoom Web skips `awaiting_admission` on immediate admission — same valid pattern as Teams.

#### Zoom SDK (`platforms/zoom/strategies/join.ts`)
1. **join.ts:12** → `await callJoiningCallback(botConfig)` — first thing
2. No `awaiting_admission` callback at all — SDK doesn't expose waiting room state
3. **meetingFlow.ts:135** → `await callStartupCallback(botConfig)`

**Correct behavior:** Zoom SDK never sends `awaiting_admission` — SDK handles admission internally. `JOINING → ACTIVE` is valid.

### 3. Unified Callback Endpoint Analysis

#### Bot side (`unified-callback.ts:42-138`)
- Sends POST to `/bots/internal/callback/status_change`
- **Fire-and-forget semantics**: although the bot `await`s the HTTP response, it doesn't act on rejection. The function returns `void` — success or failure, the bot proceeds.
- Retry: 3 attempts, exponential backoff. Logs failures but doesn't throw.
- The bot does NOT check response body for transition rejection.

#### Server side (`callbacks.py:265-398`, unified `/callback/status_change`)
- Looks up meeting by `connection_id` (session_uid)
- `await db.refresh(meeting)` to get latest state — good for consistency
- For `joining`/`awaiting_admission` (generic path, line 371-375): delegates to `update_meeting_status()` → if invalid, returns `{"status": "error"}` (bot retries)
- For `active` (special case, line 327-343): pre-checks `meeting.status in [REQUESTED, JOINING, ...]` then calls `update_meeting_status()` → if rejected (e.g., REQUESTED → ACTIVE), `success = False` BUT falls through to line 398: **returns `{"status": "processed"}` regardless!** Bot thinks callback succeeded.
- **CRITICAL BUG:** The ACTIVE handler returns "processed" even when `update_meeting_status()` returns False. No WebSocket event is published (gated on `success`), but the bot believes the status update happened.
- **SECONDARY BUG:** Webhook at line 389 fires UNCONDITIONALLY — even for rejected transitions. External webhook consumers receive status_change events for transitions that didn't happen.

#### Legacy endpoints still exist
- `/callback/started` (line 191) — duplicates `active` logic, also allows `REQUESTED → ACTIVE`
- `/callback/joining` (line 225) — delegates to `update_meeting_status()`
- `/callback/awaiting_admission` (line 245) — delegates to `update_meeting_status()`
- The bot uses `/callback/status_change` for everything (converts URL at `unified-callback.ts:69`)

### 4. Race Condition Analysis

#### Scenario 1: Fast admission (Google Meet, authenticated bot)
```
T+0ms:    Bot sends JOINING callback
T+200ms:  Server processes JOINING: REQUESTED → JOINING ✓
T+300ms:  Bot detects immediate admission, sends AWAITING_ADMISSION
T+500ms:  Server processes AWAITING_ADMISSION: JOINING → AWAITING_ADMISSION ✓
T+1300ms: Bot sends ACTIVE (after 1s delay in meetingFlow.ts:131)
T+1500ms: Server processes ACTIVE: AWAITING_ADMISSION → ACTIVE ✓
```
**Result:** Works correctly but all 3 transitions happen within ~1.5 seconds. Dashboard may only render the final "Active" state if it misses the WebSocket messages.

#### Scenario 2: JOINING callback fails all retries — ROOT CAUSE A (CRITICAL)
```
T+0ms:     Bot calls callJoiningCallback() — HTTP POST to server
           Network issue / server overloaded / 5s timeout per attempt
T+~15s:    All 3 retries exhausted (5s timeout + backoff each)
           try/catch swallows failure, bot CONTINUES with join process
T+~16s:    Bot detects admission, sends ACTIVE callback
T+~16.2s:  Server: meeting still in REQUESTED
           update_meeting_status(REQUESTED, ACTIVE) → is_valid_status_transition → False
           Handler returns {"status": "processed"} anyway (bug — see §3)
           No WebSocket published (gated on success), no Redis event
T+∞:       Dashboard stays on REQUESTED forever (until meeting ends with COMPLETED/FAILED)
```
**Impact:** Dashboard permanently stuck on REQUESTED. User never sees any status progression. This is the most severe manifestation of the bug.

#### Scenario 3: WebSocket event missed during fast transitions — ROOT CAUSE B (HIGH)
```
T+0ms:     Server processes JOINING → publishes to Redis → WebSocket event
T+50ms:    Dashboard WebSocket connection drops momentarily
T+1200ms:  Server processes ACTIVE → publishes WebSocket event
T+1300ms:  Dashboard WebSocket reconnects, receives ACTIVE event
```
**Result:** Dashboard jumps from REQUESTED to ACTIVE. JOINING event was lost during disconnect. Dashboard doesn't re-fetch current status on WebSocket reconnect. `handleStatusChange` (page.tsx:330) calls `fetchMeeting()` on ACTIVE, which gets the transition history, but `BotStatusIndicator` only uses current status — not the history.

#### Scenario 4: Intermediate states too fast to perceive — ROOT CAUSE C (MEDIUM)
```
T+0ms:     WebSocket delivers JOINING → dashboard renders step
T+1200ms:  WebSocket delivers ACTIVE → dashboard renders step
```
Everything works. JOINING visible for ~1.2 seconds. User perceives "jumped to active" if they weren't watching.

#### Scenario 5: Immediate admission — NOT A BUG
```
T+0ms:    Bot sends JOINING → Server: REQUESTED → JOINING ✓
T+500ms:  Bot detects immediate admission, skips awaiting_admission (correct)
T+1500ms: Bot sends ACTIVE → Server: JOINING → ACTIVE ✓ (valid transition)
```
This is correct for all platforms. `JOINING → ACTIVE` without `AWAITING_ADMISSION` is legitimate when there's no waiting room.

#### Scenario 6: Concurrent callbacks (no DB lock) — MEDIUM
The `update_meeting_status()` function does `meeting.status = new_status.value` then `await db.commit()`. There is NO row-level lock or SELECT FOR UPDATE. Two concurrent callbacks could both read the same `meeting.status`, both pass validation, and the second commit overwrites the first. This is a classic TOCTOU race.

### 5. Dashboard Status Display Analysis

#### BotStatusIndicator (`components/meetings/bot-status-indicator.tsx`)
- Shows a 4-step progress bar: Requested → Joining → Waiting → Recording
- Uses `STATUS_ORDER` map to determine which steps are "completed" (all steps with index < current step)
- Steps are shown as completed (green checkmark) or active (animated icon)
- **Does NOT interpolate missing states** — only renders based on current status
- If status jumps from `requested` to `active`, steps 1 (Joining) and 2 (Waiting) show as "completed" because `STATUS_ORDER.active = 3 > STATUS_ORDER.joining = 1`

**Key insight:** The dashboard doesn't show a "jump" — it shows all intermediate steps as completed checkmarks. The visual illusion is that the bot went through all states, but the intermediate states were never actually reached. The user sees the *final* status, not the progression.

#### WebSocket status handling
- `use-vexa-websocket.ts:162-169`: On `meeting.status` message, calls `setBotStatus(status)` — simply overwrites current status
- `use-live-transcripts.ts:267-279`: Same pattern — calls `updateMeetingStatus(meetingId, status)`
- `meetings-store.ts:384-398`: `updateMeetingStatus` just replaces the status field on the meeting object
- **No status queue, no interpolation, no animation between states**
- If two WebSocket messages arrive in quick succession, only the last one is rendered

#### Status history
- `StatusHistory` component imported in `meetings/[id]/page.tsx:60` — exists but was NOT found in the glob (may be defined inline or in a barrel export)
- Status transition history IS stored server-side in `meeting.data.status_transition` (array of `{from, to, timestamp, source}`)
- The `getStatusTooltipContent()` in `meeting-card.tsx` shows transition count and last update time in a tooltip
- The REST API exposes full history via `data.status_transition` — documented in cookbook

### 6. Silent Failure Audit

| Location | What's silenced | Logged? | Level | Actionable? |
|---|---|---|---|---|
| `meetings.py:137` | Invalid transition rejected | ✓ | WARNING | No — no metric, no counter |
| `callbacks.py:374-375` | Generic status update failure | Returns error response | N/A | Bot ignores response body |
| `unified-callback.ts:106` | Unexpected response status | ✓ | log() | No retry differentiation |
| `unified-callback.ts:116` | HTTP error response | ✓ | log() | Bot retries but doesn't change behavior |
| `unified-callback.ts:134` | All retries exhausted | ✓ | log() | Bot proceeds as if callback succeeded |

**Critical gap:** The bot has NO mechanism to learn that a transition was rejected. Even if the server returns `{"status": "error", "detail": "Failed to update meeting status"}`, the bot's `callStatusChangeCallback()` checks for `responseBody.status === 'processed' || 'ok' || 'container_updated'` — any other status triggers a retry, but after 3 retries it gives up silently.

**No metrics or counters exist** for rejected transitions. There's no way to measure how often this happens in production.

### 7. Related Docs Review

#### `schemas.py` docstring (line 37-40)
```
requested -> joining -> awaiting_admission -> active -> stopping -> completed
```
**Incomplete.** Missing: `NEEDS_HUMAN_HELP`, transitions from any state to `FAILED`, `JOINING → ACTIVE` (direct), `REQUESTED → STOPPING/COMPLETED`.

#### `features/bot-escalation/design.md`
- Documents escalation to `NEEDS_HUMAN_HELP` correctly
- References `checkEscalation()` in `platforms/shared/escalation.ts` — this is accurate
- Status transition section correctly shows `AWAITING_ADMISSION → NEEDS_HUMAN_HELP` and `JOINING → NEEDS_HUMAN_HELP`

#### Bot-side `MeetingStatus` type (`unified-callback.ts:3-9`)
Missing `requested` and `stopping` states. Bot only knows about: `joining`, `awaiting_admission`, `active`, `needs_human_help`, `completed`, `failed`. This is correct since the bot never sends `requested` (server sets it) or `stopping` (user API sets it).

### 8. Fix Design Options

#### Option A: Server-side callback queue
- Meeting-api buffers incoming callbacks and processes them in order
- Uses a per-meeting Redis queue + worker
- **Pros:** Guarantees ordering regardless of network timing
- **Cons:** High complexity, adds latency (~100ms per queued message), requires new infrastructure (queue worker), potential message loss if Redis goes down
- **Verdict:** Over-engineered for this problem

#### Option B: Synchronous callbacks with ordering
- Bot waits for each callback response and checks if transition was accepted
- If rejected, bot re-sends with correct intermediate state first
- **Pros:** Bot-side fix, no server changes needed
- **Cons:** Adds latency to bot flow (each callback must complete before next action), bot logic becomes complex, doesn't fix the fundamental TOCTOU race
- **Verdict:** Fragile — depends on bot being aware of state machine

#### Option C: State reconciliation (accept any forward status, fill gaps)
- Server accepts any "forward" status transition (e.g., `REQUESTED → ACTIVE`)
- Automatically inserts missing intermediate transitions into `status_transition` history
- Publishes all intermediate states to WebSocket in sequence
- **Pros:** Simple server-side change, no bot changes needed, backward compatible
- **Cons:** Intermediate states have synthetic timestamps, not "real" transitions
- **Verdict:** RECOMMENDED. Solves the visible symptom (missing states on dashboard) without adding complexity. The state machine becomes a *sequence* rather than a strict graph.

#### Option D: Optimistic state machine (accept forward jumps, publish intermediates)
- Similar to C but with explicit "gap filling" logic
- When `REQUESTED → ACTIVE` arrives, server publishes `joining` and `awaiting_admission` events to WebSocket before publishing `active`
- Each synthetic intermediate state gets a ~50ms delay between publications
- **Pros:** Dashboard always shows smooth progression
- **Cons:** Same synthetic timestamp issue as C, WebSocket messages may still arrive out of order
- **Verdict:** Viable but the 50ms delays add unnecessary latency

### 9. Root Causes Summary (numbered, with severity)

| # | Gap | Severity | Location |
|---|---|---|---|
| G1 | ACTIVE handler returns `{"status": "processed"}` on rejected transition — bot thinks callback succeeded, dashboard stays stuck | **CRITICAL** | `callbacks.py:327-398` |
| G2 | Silent rejection of invalid transitions — no error to bot, no metric | **HIGH** | `meetings.py:137-138` |
| G3 | Bot ignores callback response body — doesn't know transition was rejected | **HIGH** | `unified-callback.ts:101-114` |
| G4 | No DB-level lock on status update — TOCTOU race on concurrent callbacks | **MEDIUM** | `meetings.py:140-196` |
| ~~G5~~ | ~~Teams/Zoom skip `awaiting_admission` on immediate admission~~ — **NOT A BUG.** `JOINING → ACTIVE` is valid when no waiting room. | ~~LOW~~ | N/A |
| G6 | Dashboard `BotStatusIndicator` always shows 4 steps including "Waiting" even when `awaiting_admission` was legitimately skipped — cosmetic only, step shows as completed checkmark | **LOW** | `bot-status-indicator.tsx:30-35` |
| G7 | `/callback/started` and `/callback/status_change` have different validation for `ACTIVE` transition | **MEDIUM** | `callbacks.py:205-206 vs 328-330` |
| G8 | `MeetingStatus` docstring in `schemas.py` is incomplete | **LOW** | `schemas.py:37-40` |
| G9 | No metrics/counters for rejected transitions — can't measure problem scope | **HIGH** | All callback endpoints |

### 10. Recommended Fix

**Primary: Fix the actual bugs, not mask them with reconciliation.**

The root problem is that `JOINING` gets dropped (callback failure swallowed) and the server silently accepts this. Auto-reconciliation (Option C) would paper over the bug by inventing transitions that never happened. Instead, fix the two concrete bugs:

#### Fix 1: ACTIVE handler must return error on rejected transition (CRITICAL)
`callbacks.py:327-398` — the ACTIVE handler returns `{"status": "processed"}` even when `update_meeting_status()` returns False. Fix: return `{"status": "error", "detail": "Invalid transition: {from} → active"}` so the bot's retry logic kicks in.

#### Fix 2: Bot must propagate joining callback failure (CRITICAL)
All platform `join.ts` files wrap `callJoiningCallback()` in try/catch and continue on failure. If the joining callback failed all 3 retries, the bot should NOT proceed to send ACTIVE — the server will reject REQUESTED → ACTIVE anyway. Either:
- (a) Make `callJoiningCallback` throw on total failure (remove try/catch in join functions), OR
- (b) Track callback success in `botConfig` and re-send JOINING before ACTIVE if the original failed

#### Fix 3: Webhook fires unconditionally (MEDIUM)
`callbacks.py:389` fires webhook regardless of whether `update_meeting_status()` succeeded. Gate it on `success`.

#### Fix 4: Dashboard WebSocket reconnect (HIGH)
`use-live-transcripts.ts` doesn't re-fetch meeting status on WebSocket reconnect. Add a `fetchMeeting()` call on reconnect to sync state.

#### Fix 5: Transition rejection metrics (HIGH)
Add a counter metric in `update_meeting_status()` for rejected transitions (meeting_id, from_status, to_status). Currently only a WARNING log with no structured data.

**Additional cosmetic fix:**
- G6: `BotStatusIndicator` could omit the "Waiting" step when `awaiting_admission` was never reached, but this is low priority — the current checkmark display is technically correct.

## DoD (refined after research)

### Prerequisites
- [ ] Root cause confirmed: reproduce REQUESTED → ACTIVE jump with a real bot (simulate JOINING callback failure)

### Server-side fixes
- [ ] **Fix 1:** ACTIVE handler in `callbacks.py` returns `{"status": "error"}` when `update_meeting_status()` returns False (currently returns "processed")
- [ ] **Fix 3:** Webhook delivery in ACTIVE handler gated on `success` flag (currently fires unconditionally)
- [ ] **Fix 5:** Add structured metric/counter for rejected transitions in `update_meeting_status()` (meeting_id, from_status, to_status)
- [ ] Rejected transitions logged at ERROR level (not WARNING)

### Bot-side fixes
- [ ] **Fix 2:** `callJoiningCallback()` failure propagates — bot does NOT proceed to send ACTIVE when JOINING callback failed all retries
- [ ] Platform join functions (`googlemeet/join.ts`, `msteams/join.ts`, `zoom/web/join.ts`, `zoom/strategies/join.ts`) surface joining callback failure instead of swallowing it

### Dashboard fixes
- [ ] **Fix 4:** WebSocket reconnect triggers `fetchMeeting()` to sync status (currently no re-fetch on reconnect)
- [ ] (Optional, LOW) `BotStatusIndicator` omits "Waiting" step when meeting never entered `awaiting_admission`

### Verification
- [ ] Google Meet bot (with waiting room): dashboard shows REQUESTED → JOINING → AWAITING_ADMISSION → ACTIVE
- [ ] Teams bot (immediate admission): dashboard shows REQUESTED → JOINING → ACTIVE (skipping awaiting_admission is correct)
- [ ] Simulated JOINING callback failure: bot retries, fails, does NOT send ACTIVE → server stays in REQUESTED → bot reports error (not silent)
- [ ] ACTIVE handler returns error response when transition is invalid → bot retries or reports failure
- [ ] WebSocket reconnect: dashboard syncs to current status after reconnect
- [ ] No spurious webhook deliveries for rejected transitions
- [ ] Rejected transition counter increments on invalid attempts
