# Bot Escalation Design

When a meeting bot is blocked (CAPTCHA, auth wall, waiting room timeout, unexpected UI), it escalates to the user via VNC instead of failing silently.

---

## 1. Detection — What Triggers Escalation

Each platform already has admission polling loops that detect blocking conditions. Escalation hooks into these existing patterns.

### Trigger Conditions (per platform)

| Platform | Trigger | Detection Point | Current Behavior |
|----------|---------|-----------------|------------------|
| **Zoom** | Waiting room timeout approaching | `waitForZoomWebAdmission()` poll loop, after 80% of `waitingRoomTimeout` elapsed | Throws timeout error, bot exits |
| **Zoom** | CAPTCHA / unexpected UI | `isAdmitted()` + `isInWaitingRoom()` both false for >10s (neither admitted nor in known waiting state) | Falls through to timeout |
| **Google Meet** | Waiting room timeout approaching | `waitForGoogleMeetingAdmission()` poll loop, same 80% threshold | Throws timeout error |
| **Google Meet** | "Ask to join" button stuck / auth wall | `checkForGoogleAdmissionIndicators()` + `checkForWaitingRoomIndicators()` both false | Falls through to timeout |
| **Teams** | Waiting room timeout approaching | `waitForTeamsMeetingAdmission()` poll loop, same 80% threshold | Throws timeout error |
| **Teams** | Unexpected pre-join state | Neither lobby text, join button, nor leave button visible for >10s | Falls through to 30s polling, then timeout |
| **All** | Join phase error (non-crash) | `strategies.join()` throws but page is still alive | Calls `gracefulLeaveFunction` immediately |

### Escalation Decision Logic

```
function shouldEscalate(elapsedMs, timeoutMs, page):
  # Condition 1: Timeout approaching in waiting room
  if elapsedMs > timeoutMs * 0.8:
    return { reason: "waiting_room_timeout_approaching", urgency: "high" }

  # Condition 2: Unknown state (not admitted, not in waiting room, not rejected)
  if not isAdmitted(page) and not isInWaitingRoom(page) and not isRejected(page):
    unknownStateDuration += pollInterval
    if unknownStateDuration > 10_000:  # 10s in unknown state
      return { reason: "unknown_blocking_state", urgency: "critical" }

  # Condition 3: Join error with live page
  if joinFailed and page.isConnected():
    return { reason: "join_error_page_alive", urgency: "critical" }

  return null  # No escalation needed
```

### Where Detection Lives

**File:** `services/vexa-bot/core/src/platforms/shared/escalation.ts` (new)

This module exports a single function `checkEscalation(page, elapsedMs, timeoutMs, platformChecks)` that each platform's admission loop calls during its poll cycle. Platform-specific checks (`isAdmitted`, `isInWaitingRoom`, `isRejected`) are passed in as callbacks — the escalation module is platform-agnostic.

**Integration points** (existing files, minimal changes):
- `zoom/web/admission.ts:95-110` — add `checkEscalation()` call inside the `while` poll loop
- `googlemeet/admission.ts:147-175` — add `checkEscalation()` call inside the waiting room `while` loop
- `googlemeet/admission.ts:188-222` — add `checkEscalation()` call inside the polling `while` loop
- `msteams/admission.ts:150-192` — add `checkEscalation()` call inside the waiting room `while` loop

Each platform's admission function gains one extra `if` branch: if `checkEscalation()` returns non-null, call `triggerEscalation()` (see below) instead of continuing to poll.

---

## 2. Notification — WebSocket Push to Dashboard

### New Status: `needs_human_help`

**Add to `MeetingStatus` enum** in `libs/shared-models/shared_models/schemas.py`:

```python
class MeetingStatus(str, Enum):
    REQUESTED = "requested"
    JOINING = "joining"
    AWAITING_ADMISSION = "awaiting_admission"
    ACTIVE = "active"
    NEEDS_HUMAN_HELP = "needs_human_help"   # <-- NEW
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
```

**Valid transitions into `NEEDS_HUMAN_HELP`:**
- `AWAITING_ADMISSION -> NEEDS_HUMAN_HELP` (waiting room timeout approaching)
- `JOINING -> NEEDS_HUMAN_HELP` (unknown blocking state during join)

**Valid transitions out of `NEEDS_HUMAN_HELP`:**
- `NEEDS_HUMAN_HELP -> ACTIVE` (user resolved, bot continues)
- `NEEDS_HUMAN_HELP -> FAILED` (user gave up or VNC timeout)
- `NEEDS_HUMAN_HELP -> STOPPING` (user stops bot)
- `NEEDS_HUMAN_HELP -> COMPLETED` (user stops bot)

### Bot-Side Callback

**File:** `services/vexa-bot/core/src/utils.ts`

Add:
```typescript
export async function callNeedsHumanHelpCallback(
  botConfig: any,
  reason: string,
  screenshotPath?: string
): Promise<void> {
  await callStatusChangeCallback(botConfig, "needs_human_help", {
    escalation_reason: reason,
    screenshot_path: screenshotPath,
    vnc_ready: true,  // VNC is always available in meeting bot containers
    escalated_at: new Date().toISOString()
  });
}
```

### Bot-Manager Handling

**File:** `services/bot-manager/app/main.py`, in `bot_status_change_callback()`:

When `new_status == "needs_human_help"`:
1. Update meeting status in DB
2. Store escalation metadata in `meeting.data` JSONB: `{ escalation: { reason, vnc_url, escalated_at } }`
3. Generate VNC access URL: build `browser_session:{token}` Redis entry pointing to the bot's container (reuse existing `resolve_browser_session` infrastructure)
4. Publish via `publish_meeting_status_change()` — this already pushes to the dashboard WebSocket

### WebSocket Event Payload

The existing WebSocket infrastructure at `api-gateway/main.py` already forwards `meeting.status` events. The dashboard receives:

```json
{
  "type": "meeting.status",
  "meeting_id": 42,
  "status": "needs_human_help",
  "data": {
    "escalation_reason": "waiting_room_timeout_approaching",
    "vnc_url": "/b/{session_token}",
    "escalated_at": "2026-03-25T10:30:00Z"
  }
}
```

### Dashboard UI

**File:** `services/dashboard/src/components/meetings/bot-status-indicator.tsx`

Add `needs_human_help` to the status indicator with a distinct visual (pulsing amber/orange). When this status is active, show an "Intervene" button that opens the VNC URL in a new tab or inline iframe.

**File:** `services/dashboard/src/app/meetings/[id]/page.tsx`

When meeting status is `needs_human_help`, render an escalation banner:
```
[!] Bot needs help — [reason]. Click to take control via remote browser.
[Open Remote Browser]  [Dismiss & Let Bot Retry]  [Stop Bot]
```

---

## 3. VNC Handoff — Start VNC On Demand in Meeting Bots

### Key Insight: VNC Stack Already Exists

The `entrypoint.sh` already has full VNC infrastructure (Xvfb, fluxbox, x11vnc, websockify, socat for CDP) — but only starts it in `browser_session` mode. Meeting bots run with `Xvfb :99` but skip the VNC stack.

### Design: Always-Ready VNC (Lazy Start)

**Option A (recommended): Start VNC stack lazily on escalation**

Meeting bots already have Xvfb running (`Xvfb :99 -screen 0 1920x1080x24`). The browser is rendering to this virtual display. VNC just exposes what's already there.

When escalation triggers:
1. Bot spawns VNC stack via child process (same commands as `entrypoint.sh` browser_session block):
   ```bash
   x11vnc -display :99 -forever -nopw -shared -rfbport 5900 &
   websockify 6080 localhost:5900 &
   ```
2. Bot writes `browser_session:{token}` to Redis (token = meeting's session token or a newly generated one)
3. VNC is accessible within ~1 second

**Why lazy over always-on:** Meeting bots are high-frequency. Running VNC on every bot wastes ~20MB RAM per container and opens an unnecessary attack surface. Starting on-demand adds ~1s latency, which is acceptable since the user still needs to click through the notification.

### Implementation

**File:** `services/vexa-bot/core/src/platforms/shared/escalation.ts` (new)

```typescript
import { spawn } from 'child_process';

let vncStarted = false;

export async function startVncStack(): Promise<void> {
  if (vncStarted) return;

  // x11vnc — expose existing Xvfb display
  spawn('x11vnc', ['-display', ':99', '-forever', '-nopw', '-shared', '-rfbport', '5900'], {
    stdio: 'ignore', detached: true
  }).unref();

  // websockify — bridge VNC to WebSocket for noVNC
  const novncDir = '/usr/share/novnc';
  const wsArgs = existsSync(novncDir)
    ? ['--web', novncDir, '6080', 'localhost:5900']
    : ['6080', 'localhost:5900'];
  spawn('websockify', wsArgs, { stdio: 'ignore', detached: true }).unref();

  // Wait for VNC to be ready
  await waitForPort(5900, 3000);
  vncStarted = true;
}
```

### Container Port Exposure

Meeting bot containers currently don't expose port 6080 (websockify/noVNC) or 5900 (VNC). Two approaches:

**Option A (recommended): Expose ports at container creation time, always.**
Add `6080` to the exposed ports list in `orchestrator_utils.py` for meeting bots. The port is exposed but nothing listens until escalation triggers VNC start. Cost: zero (Docker port mapping is cheap when nothing binds).

**Option B: Use CDP proxy (9223) which is already exposed.**
The socat CDP proxy is already started in browser_session mode. Not applicable here since we need VNC, not CDP.

### Redis Session Registration

When VNC starts, the bot registers itself for the gateway to discover:

```typescript
// In escalation.ts
async function registerVncSession(botConfig: BotConfig): Promise<string> {
  const token = botConfig.session_token || crypto.randomUUID();
  const sessionData = {
    container_name: botConfig.container_name,
    meeting_id: botConfig.meeting_id,
    user_id: botConfig.user_id,
    escalation: true
  };
  // Write to Redis — bot-manager callback handler does this
  // Bot sends the token in the needs_human_help callback payload
  return token;
}
```

The bot-manager receives the callback and writes `browser_session:{token}` to Redis, exactly as it does for `browser_session` mode containers. The api-gateway's existing `/b/{token}` routes (lines 1016-1400) immediately serve VNC access.

---

## 4. Resume — Bot Detects Resolution and Continues

### The Critical Flow

```
Bot polling (waiting room) → Escalation triggered → VNC starts → Status: needs_human_help
  → User opens VNC, admits bot / solves CAPTCHA
  → Bot's admission poll detects it's admitted
  → Bot sends "active" callback → Status: active
  → Meeting continues normally (recording, transcription, etc.)
```

### Why This Works Without Special Resume Logic

The admission poll loop is STILL RUNNING while the user intervenes via VNC. The escalation does NOT stop the poll — it just:
1. Starts VNC
2. Sends a status callback
3. Extends the timeout (gives the user time to act)

The existing admission code already handles the "suddenly admitted" case:
- Zoom: `if (await isAdmitted(page))` on line 103 of `zoom/web/admission.ts`
- Google Meet: `if (admissionFound)` check in the poll loop
- Teams: `if (leaveButtonNowFound)` check in the poll loop

### Timeout Extension

When escalation triggers, the admission timeout is extended:

```typescript
// In the admission poll loop, after escalation:
const originalTimeout = timeoutMs;
const escalationExtension = 5 * 60 * 1000; // 5 minutes for user to intervene
timeoutMs = elapsedMs + escalationExtension;  // Reset from current position
```

This prevents the bot from timing out while the user is actively trying to help.

### What If The User Doesn't Help?

After the extended timeout expires:
1. Bot sends `failed` callback with `completion_reason: "escalation_timeout"`
2. VNC remains accessible for a grace period (2 min) so user can see the final state
3. Bot exits normally via `gracefulLeaveFunction`

### What If The User Solves It?

1. Admission poll detects admission → calls `callStartupCallback` (status: `active`)
2. `meetingFlow.ts` continues: starts recording, removal monitor, etc.
3. VNC stays running (it's lightweight) — user can continue to observe if they want
4. Meeting proceeds normally to completion

### Edge Case: User Solves a Non-Admission Block

If the block was a CAPTCHA or auth wall (not a waiting room), the bot may be in an unknown state after the user interacts. The admission poll will detect the result:
- If user got the bot into the meeting → `isAdmitted()` returns true → resume
- If user navigated to a different page → `isAdmitted()` returns false, loop continues polling
- If user closed the meeting tab → page disconnects → bot catches error, exits

---

## 5. Architecture — Where Code Lives

### New Files

| File | Purpose |
|------|---------|
| `services/vexa-bot/core/src/platforms/shared/escalation.ts` | Detection logic, VNC lazy start, `triggerEscalation()` orchestrator |
| `features/bot-escalation/README.md` | Feature documentation |
| `features/bot-escalation/.claude/CLAUDE.md` | Agent instructions for this feature |

### Modified Files

| File | Change |
|------|--------|
| `libs/shared-models/shared_models/schemas.py` | Add `NEEDS_HUMAN_HELP` to `MeetingStatus`, update transitions |
| `services/vexa-bot/core/src/utils.ts` | Add `callNeedsHumanHelpCallback()` |
| `services/vexa-bot/core/src/platforms/zoom/web/admission.ts` | Add `checkEscalation()` in poll loop |
| `services/vexa-bot/core/src/platforms/googlemeet/admission.ts` | Add `checkEscalation()` in poll loops |
| `services/vexa-bot/core/src/platforms/msteams/admission.ts` | Add `checkEscalation()` in poll loops |
| `services/bot-manager/app/main.py` | Handle `needs_human_help` status in callback, register VNC session in Redis |
| `services/bot-manager/app/orchestrator_utils.py` | Expose port 6080 on meeting bot containers |
| `services/dashboard/src/components/meetings/bot-status-indicator.tsx` | Add `needs_human_help` visual state |
| `services/dashboard/src/app/meetings/[id]/page.tsx` | Add escalation banner with VNC link |
| `services/dashboard/src/types/vexa.ts` | Add `needs_human_help` to `MeetingStatus` type |

### Data Flow

```
                  Bot Container                    Bot Manager              Dashboard
                  ============                     ===========              =========
  [admission poll loop]
        |
  checkEscalation() → non-null
        |
  startVncStack()  (ports 5900, 6080)
        |
  callNeedsHumanHelpCallback()
        |
        +--- HTTP POST /callback --→  bot_status_change_callback()
                                            |
                                      Update meeting.status = needs_human_help
                                      Write browser_session:{token} to Redis
                                            |
                                      publish_meeting_status_change()
                                            |
                                            +--- Redis PubSub --→  WebSocket push
                                                                        |
                                                                   onStatusChange("needs_human_help")
                                                                        |
                                                                   Show escalation banner
                                                                   [Open VNC: /b/{token}]
                                                                        |
  User interacts via VNC ←──── noVNC iframe ←──── api-gateway /b/{token}/vnc/*
        |
  [admission poll still running]
  isAdmitted() → true
        |
  callStartupCallback()  (status: active)
        |
  Normal meeting flow continues
```

### Dependencies

- **No new services.** Reuses existing VNC/noVNC/websockify binaries already in the bot container image.
- **No new Redis data structures.** Reuses `browser_session:{token}` pattern.
- **No new WebSocket channels.** Reuses `meeting.status` event type.
- **No new API endpoints.** Reuses `/b/{token}` browser session routes in api-gateway.

### Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| VNC start fails in meeting container | x11vnc/websockify are already installed (Dockerfile). If start fails, bot logs error and continues normal timeout behavior — escalation is best-effort |
| Port 6080 not reachable from gateway | Pre-expose port at container creation; if docker networking blocks it, fall back to screenshot-only escalation (send screenshot in callback payload) |
| User breaks bot state via VNC | Admission poll is read-only detection. Even if user navigates away, the poll will either detect admission or timeout. No special recovery needed |
| Race: user admits bot just as escalation fires | Harmless — bot gets admitted, sends `active` callback, `needs_human_help` status is immediately superseded. Dashboard shows `active` |
| Multiple escalations for same meeting | Guard: `escalationTriggered` boolean prevents re-entry. One escalation per admission attempt |

### Future Extensions

- **Screenshot-only mode:** For environments where VNC isn't available, send a screenshot with the callback instead of a VNC URL. Dashboard shows the screenshot with "this is what the bot sees" context.
- **Agent-assisted resolution:** Instead of (or before) human escalation, try an AI agent to solve CAPTCHAs or navigate auth flows via CDP.
- **Notification channels:** Push escalation alerts to Slack, Telegram, email — not just the dashboard.
- **Auto-retry with different strategy:** If escalation was due to CAPTCHA, auto-retry with a different browser profile or user agent.

---

## 6. Credential Persistence — Save Authenticated State for Future Bots

### The Pattern

When a user resolves an escalation (solves CAPTCHA, logs into Zoom/Google/Teams), the browser now has authenticated cookies and session state. This state should be **saved** so future bots from the same user skip the auth/CAPTCHA entirely.

This is the same S3 sync infrastructure used by browser sessions:
- `s3://vexa-agentic/users/{user_id}/browser-userdata/` stores Chrome profile data
- Bot startup: `s3-sync.ts` downloads the profile → `/tmp/browser-data/`
- The browser launches with `--user-data-dir=/tmp/browser-data` → cookies, localStorage, sessions restored

### Flow: Escalation → Save → Reuse

```
1. Bot hits CAPTCHA/auth → escalates to user via VNC
2. User solves CAPTCHA / logs into Zoom account via VNC
3. Dashboard shows "Save Browser State" button (already exists in browser session view)
4. User clicks Save → browser state synced to S3: s3://users/{id}/browser-userdata/
5. Next bot for the same user downloads this profile on startup
6. Bot joins with authenticated cookies → no CAPTCHA, no auth wall
```

### What Exists Already

- **S3 sync service:** `services/vexa-bot/core/src/s3-sync.ts` — handles upload/download of browser profiles to MinIO
- **Save endpoint:** `POST /b/{token}/save` → proxies to `bot-manager/internal/browser-sessions/{token}/save`
- **Bot startup sync:** `entrypoint.sh` calls S3 sync down on startup (browser_session mode)
- **Dashboard Save button:** `browser-session-view.tsx` has "Save Storage" button

### What Needs to Change

1. **Meeting bots should also sync down browser profiles on startup** — currently only `browser_session` mode does this. Meeting bots should check if `s3://users/{user_id}/browser-userdata/` exists and download it.

2. **Save button in escalation banner** — when VNC is active during escalation, dashboard shows "Save Browser State" alongside "Open Remote Browser". This lets the user persist their auth after resolving.

3. **Auto-save on escalation resolution** — when the bot transitions from `needs_human_help` → `active` (user resolved), automatically save the browser state. The user's auth is likely fresh and worth preserving.

4. **Per-platform profile isolation** — browser profiles may conflict between platforms (Zoom cookies vs GMeet cookies). Consider per-platform storage: `s3://users/{id}/browser-userdata/{platform}/`

### Implementation Plan

**MVP0 (escalation only):** Bot escalates, user resolves. No credential saving — bots hit the same issue next time. This is what we're building now.

**MVP1 (manual save):** Add "Save Browser State" button to escalation banner. User explicitly saves after resolving. Next bot for same user gets authenticated profile.

**MVP2 (auto-save on resolution):** When `needs_human_help → active` transition fires, automatically trigger S3 save. No user action needed.

**MVP3 (per-platform profiles):** Isolate browser profiles per platform so Zoom auth doesn't interfere with GMeet cookies.

**MVP4 (bot startup sync for meeting bots):** Meeting bots (not just browser sessions) download the user's browser profile on startup. This is where bots "learn" to use saved credentials.
