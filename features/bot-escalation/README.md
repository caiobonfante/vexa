# Bot Escalation

> **Confidence: 0** — Design complete, not yet implemented.
> **Tested:** Nothing yet.
> **Not tested:** Detection, VNC lazy-start, dashboard UI, timeout/retry.
>
> **Agent manifest:** [CLAUDE.md](.claude/CLAUDE.md) | [findings](tests/findings.md) | [feature-log](tests/feature-log.md)

## Why

Every meeting bot can hit CAPTCHA, auth walls, or admission issues on any platform. Currently the bot fails silently — the user sees "failed" with no context and no recourse. Bot escalation gives the user a chance to intervene: the bot detects it's stuck, starts a VNC session on demand, and notifies the user via the dashboard. The user takes control of the browser, solves the problem, and the bot resumes automatically.

Platform-universal — works on Zoom, Google Meet, Teams, and future platforms. Reuses existing browser session VNC infrastructure (x11vnc, websockify, noVNC) already installed in bot containers.

## What

### Detection: When Does the Bot Escalate?

Each platform's admission polling loop already detects blocking conditions. Escalation hooks into these existing patterns via a single `checkEscalation()` call added to each platform's poll loop.

**Trigger conditions per platform:**

| Platform | Trigger | Detection Point | Current Behavior |
|----------|---------|-----------------|------------------|
| **Zoom** | Waiting room timeout approaching (80% elapsed) | `waitForZoomWebAdmission()` poll loop | Throws timeout, bot exits |
| **Zoom** | CAPTCHA / unexpected UI (unknown state >10s) | `isAdmitted()` + `isInWaitingRoom()` both false | Falls through to timeout |
| **Google Meet** | Waiting room timeout approaching | `waitForGoogleMeetingAdmission()` poll loop | Throws timeout |
| **Google Meet** | "Ask to join" stuck / auth wall | Both admission + waiting room indicators false | Falls through to timeout |
| **Teams** | Waiting room timeout approaching | `waitForTeamsMeetingAdmission()` poll loop | Throws timeout |
| **Teams** | Unexpected pre-join state (>10s) | No lobby, join button, or leave button visible | Falls through to timeout |
| **All** | Join phase error (non-crash) | `strategies.join()` throws but page still alive | Immediate graceful leave |

### Escalation Decision Logic

```
shouldEscalate(elapsedMs, timeoutMs, page):
  if elapsedMs > timeoutMs * 0.8:       → "waiting_room_timeout_approaching" (high)
  if unknownState > 10s:                 → "unknown_blocking_state" (critical)
  if joinFailed and page.isConnected():  → "join_error_page_alive" (critical)
```

### Architecture: Detection -> Notification -> VNC Handoff -> Resume

```
Bot Container                    Bot Manager              Dashboard
============                     ===========              =========
[admission poll loop]
      |
checkEscalation() → non-null
      |
VNC already running (started in entrypoint for all bots)
      |
callNeedsHumanHelpCallback()
      |
      +--- HTTP POST /callback --→  bot_status_change_callback()
                                          |
                                    Update meeting.status = needs_human_help
                                    Container already in Redis as browser_session:{meeting_id}
                                          |
                                    publish_meeting_status_change()
                                          |
                                          +--- Redis PubSub --→  WebSocket push
                                                                      |
                                                                 Show escalation banner
                                                                 [Open VNC: /b/{token}]
                                                                      |
User interacts via VNC ←──── noVNC iframe ←──── api-gateway /b/{token}/vnc/*
      |
[admission poll STILL RUNNING]
isAdmitted() → true
      |
callStartupCallback() (status: active)
      |
Normal meeting flow continues
```

The admission poll loop keeps running during escalation. When the user solves the problem (admits the bot, solves CAPTCHA), the existing admission detection picks it up automatically. No special resume logic needed.

### New Status: `needs_human_help`

Added to `MeetingStatus` enum in `schemas.py`:

- **Into:** `AWAITING_ADMISSION -> NEEDS_HUMAN_HELP`, `JOINING -> NEEDS_HUMAN_HELP`
- **Out of:** `NEEDS_HUMAN_HELP -> ACTIVE` (resolved), `-> FAILED` (timeout), `-> STOPPING` (user stops)

### VNC Already Running

Since the unified bot/browser architecture, every meeting bot starts with VNC (fluxbox + x11vnc + websockify) in the entrypoint. No lazy-start needed — VNC is already active when escalation triggers. The container is also already registered in Redis by meeting ID, so the gateway can proxy VNC immediately.

### Components

| Component | Role | Key File |
|-----------|------|----------|
| **escalation** | Detection logic, `triggerEscalation()` (VNC already running) | `services/vexa-bot/core/src/platforms/shared/escalation.ts` (new) |
| **bot callback** | `callNeedsHumanHelpCallback()` sends status | `services/vexa-bot/core/src/utils.ts` (modified) |
| **meeting-api** | Handles `needs_human_help` callback, escalation metadata in meeting.data | `packages/meeting-api/meeting_api/callbacks.py` (modified) |
| **schemas** | `NEEDS_HUMAN_HELP` status + valid transitions | `packages/meeting-api/meeting_api/schemas.py` (modified) |
| **dashboard** | Escalation banner + VNC link on meeting page | `services/dashboard/src/app/meetings/[id]/page.tsx` (modified) |
| **bot-status-indicator** | Pulsing amber state for `needs_human_help` | `services/dashboard/src/components/meetings/bot-status-indicator.tsx` (modified) |

### Dependencies

No new services, APIs, Redis structures, or WebSocket channels. Reuses:
- VNC stack already running in every bot container (unified architecture)
- `browser_session:{meeting_id}` Redis key already set at bot creation
- `meeting.status` WebSocket event type
- `/b/{meeting_id}` gateway routes for VNC proxy

### Timeout and Retry

When escalation triggers, the admission timeout extends by 5 minutes. If the user doesn't intervene:
1. Extended timeout expires
2. Bot sends `failed` callback with `completion_reason: "escalation_timeout"`
3. VNC stays accessible for 2 min grace period (user can see final state)
4. Bot exits via `gracefulLeaveFunction`

Guard: `escalationTriggered` boolean prevents multiple escalations per admission attempt.

## How

### MVP Ladder

| MVP | What it proves | Status |
|-----|---------------|--------|
| MVP0 | Detection + `needs_human_help` status callback fires on waiting room timeout | Not started |
| MVP1 | VNC lazy-start works — user can see bot's browser via `/b/{token}` | Not started |
| MVP2 | Dashboard shows escalation banner with "Open Remote Browser" + "Save Browser State" | Not started |
| MVP3 | Credential persistence — save browser state on escalation resolution, reuse on next bot | Not started |
| MVP4 | Meeting bots download user's browser profile on startup (authenticated joins) | Not started |
| MVP5 | Timeout extension + auto-retry + graceful degradation | Not started |

### Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| VNC start fails in meeting container | x11vnc/websockify already installed. If start fails, bot logs error and continues normal timeout — escalation is best-effort |
| Port 6080 not reachable from gateway | Pre-expose at container creation. Fallback: screenshot-only escalation (send screenshot in callback payload) |
| User breaks bot state via VNC | Admission poll is read-only detection. Even if user navigates away, poll either detects admission or times out |
| Race: user admits bot just as escalation fires | Harmless — bot gets admitted, sends `active`, `needs_human_help` is immediately superseded |

### Credential Persistence — Save & Reuse Authenticated State

When a user resolves an escalation (solves CAPTCHA, logs into Zoom/Google), the browser has authenticated cookies. These should be **saved** so future bots skip auth entirely.

**The flow:**
```
Bot escalates → user solves CAPTCHA via VNC → clicks "Save Browser State"
→ browser profile saved to S3: s3://users/{user_id}/browser-userdata/
→ next bot downloads profile on startup → joins with cookies → no CAPTCHA
```

**What exists:** S3 sync (`s3-sync.ts`), save endpoint (`POST /b/{token}/save`), dashboard save button — all built for browser sessions. Meeting bots just need to participate in the same sync.

**MVP ladder for credentials:**

| MVP | Gate |
|-----|------|
| MVP0 | Escalation works, no credential saving (current) |
| MVP1 | "Save Browser State" button in escalation banner → manual save |
| MVP2 | Auto-save when `needs_human_help → active` transition fires |
| MVP3 | Per-platform profile isolation (`s3://users/{id}/browser-userdata/{platform}/`) |
| MVP4 | Meeting bots download user's browser profile on startup (bots "learn" to use saved credentials). Note: Google Meet works. Teams requires M365 Business account — consumer accounts get locked by Microsoft. See `conductor/missions/research-msteams-auth.md`. |

### Future Extensions

- **Screenshot-only mode:** For environments without VNC, send screenshot with callback instead of VNC URL
- **Agent-assisted resolution:** AI agent solves CAPTCHAs or navigates auth flows via CDP before escalating to human
- **Notification channels:** Push escalation alerts to Slack, Telegram, email — not just the dashboard
- **Auto-retry with different strategy:** On CAPTCHA, retry with different browser profile or user agent

### Verify

1. Start agentic stack: `cd features/agentic-runtime/deploy && docker compose up -d`
2. Create a meeting where the bot will be stuck in waiting room
3. Verify `needs_human_help` status appears in dashboard within expected timeout threshold
4. Click "Open Remote Browser" — verify VNC shows the bot's browser
5. Admit the bot manually via VNC — verify bot resumes and meeting becomes `active`
6. Test timeout: don't intervene — verify bot fails gracefully after extended timeout
