# Bot Escalation — Validation Report

**Date:** 2026-03-25
**Validator:** validator agent
**Tasks validated:** #1 (Alpha), #2 (Beta), #3 (Gamma)

## Summary

The bot escalation feature is **mostly complete** with two issues found:
1. **BUILD BLOCKER** — Dashboard fails to compile (missing `needs_human_help` in admin page)
2. **FUNCTIONAL BUG** — VNC button will never render (session_token not stored in escalation data)

---

## Checklist

### 1. TypeScript Compilation
- **Result: FAIL**
- `npx tsc --noEmit` in `services/vexa-bot/core/` — PASS (clean, no errors)
- `npx next build` in `services/dashboard/` — **FAIL**
- Error: `src/app/admin/bots/page.tsx:46` — `STATUS_CONFIG` record missing `needs_human_help` entry
- The `MeetingStatus` type was updated in `vexa.ts` but the admin bots page wasn't updated to match

### 2. Python: schemas.py
- **Result: PASS**
- `NEEDS_HUMAN_HELP = "needs_human_help"` added to `MeetingStatus` enum (line 55)
- Valid transitions INTO: `JOINING -> NEEDS_HUMAN_HELP` (line 99), `AWAITING_ADMISSION -> NEEDS_HUMAN_HELP` (line 106)
- Valid transitions OUT: `NEEDS_HUMAN_HELP -> ACTIVE`, `-> FAILED`, `-> STOPPING` (lines 111-114)
- Bot callback transitions include all escalation paths (lines 172-175)

### 3. escalation.ts
- **Result: PASS**
- File: `services/vexa-bot/core/src/platforms/shared/escalation.ts`
- Exports: `checkEscalation`, `triggerEscalation`, `startVncStack`, `getEscalationExtensionMs`, `wasEscalationTriggered`, `resetEscalation`
- `checkEscalation` — guards with `escalationTriggered` boolean, checks 3 conditions (timeout approaching, unknown state >10s, join error with live page)
- `triggerEscalation` — idempotent, starts VNC then calls `callNeedsHumanHelpCallback`
- `startVncStack` — spawns x11vnc + websockify, waits for port 5900 (3s timeout)
- `getEscalationExtensionMs` — returns 5 min extension when escalation is active
- `waitForPort` — internal helper, properly handles connect/error/timeout

### 4. Admission files: checkEscalation integration
- **Zoom** (`platforms/zoom/web/admission.ts`): PASS
  - Import: `checkEscalation, triggerEscalation, getEscalationExtensionMs` (line 5)
  - Poll loop: tracks `unknownStateDuration`, calls `checkEscalation` + `triggerEscalation` (lines 119-124)
  - Timeout: uses `effectiveTimeout()` with escalation extension (line 98)
- **Google Meet** (`platforms/googlemeet/admission.ts`): PASS
  - Import: same 3 functions (line 4)
  - Two poll loops both have escalation checks:
    - Waiting room loop (lines 180-183)
    - Polling loop (lines 239-242)
  - Both use `effectiveTimeout()` with extension
- **Teams** (`platforms/msteams/admission.ts`): PASS
  - Import: same 3 functions (line 4)
  - Poll loop: tracks `unknownStateDuration`, calls `checkEscalation` + `triggerEscalation` (lines 197-200)

### 5. utils.ts: callNeedsHumanHelpCallback
- **Result: PASS**
- File: `services/vexa-bot/core/src/utils.ts` (lines 21-27)
- Calls `callStatusChangeCallback(botConfig, "needs_human_help", reason)`
- Imported and used by `escalation.ts`

### 6. meeting-api: needs_human_help handling
- **Result: PASS (with caveat — see bug #2)**
- File: `services/meeting-api/app/main.py` (lines 2024-2064)
- `elif new_status == MeetingStatus.NEEDS_HUMAN_HELP:` block handles:
  - Updates meeting status via `update_meeting_status()`
  - Stores escalation metadata in `meeting.data['escalation']` JSONB
  - Generates session token via `secrets.token_urlsafe(24)`
  - Writes `browser_session:{token}` to Redis with 1h TTL
  - Publishes via `publish_meeting_status_change()` with extra escalation data
- `ACTIVE` transition handler (line 2008) accepts `NEEDS_HUMAN_HELP.value` as valid source
- **BUG:** Session token is NOT stored in `meeting.data['escalation']` — only `vnc_url` (which is `/b/{token}`) is stored. Dashboard expects `escalation.session_token`.

### 7. orchestrator_utils.py: port 6080 on meeting bots
- **Result: PASS**
- `PortBindings` includes `"6080/tcp": [{"HostPort": "0"}]` (line 329) — dynamic host port
- `ExposedPorts` includes `"6080/tcp": {}` (line 362)
- Comment explains: "VNC/noVNC for escalation (dynamic host port, nothing listens until escalation)"

### 8. Dashboard: vexa.ts + page.tsx
- **vexa.ts: PASS**
  - `MeetingStatus` type includes `"needs_human_help"` (line 10)
  - `statusConfig` has `needs_human_help` entry with orange styling (line 276)
  - `getStatusInfo()` handles `needs_human_help` with description from `escalation_reason` (lines 369-376)
- **page.tsx: PASS (with caveat — see bug #2)**
  - Escalation banner renders when `status === "needs_human_help"` (lines 1570-1620+)
  - Shows reason, "Open Remote Browser" button, "Save Browser State" button
  - VNC URL construction is correct format
  - **BUG:** Reads `escalation?.session_token` but meeting-api never stores `session_token` in escalation — only stores `vnc_url`. The VNC button will never render.
- **bot-status-indicator.tsx: PASS**
  - `needs_human_help` has sort order 2.5 (between awaiting_admission and active)
- **admin/bots/page.tsx: FAIL**
  - `STATUS_CONFIG` record is typed `Record<MeetingStatus, ...>` but missing `needs_human_help` entry

### 9. meetingFlow.ts: No regressions
- **Result: PASS**
- No modifications to `meetingFlow.ts` — escalation hooks into admission loops only
- The poll loop continues running during escalation, so normal admission detection works unchanged

---

## Issues Found

### BLOCKER: Dashboard build fails

**File:** `services/dashboard/src/app/admin/bots/page.tsx:46`
**Issue:** `STATUS_CONFIG` is typed `Record<MeetingStatus, ...>` but doesn't include `needs_human_help`
**Fix:** Add entry:
```typescript
needs_human_help: { label: "Needs Help", color: "bg-orange-100 text-orange-700", icon: AlertTriangle },
```
(`AlertTriangle` is already imported on line 13)

### BUG: VNC button won't render in dashboard

**File:** `services/meeting-api/app/main.py:2038-2046`
**Issue:** Bot-manager stores `escalation.vnc_url = "/b/{token}"` but NOT `escalation.session_token = token`. Dashboard (`page.tsx:1589`) reads `escalation?.session_token` which is always `undefined`.
**Fix:** Add `meeting_data['escalation']['session_token'] = session_token` after line 2044:
```python
session_token = secrets.token_urlsafe(24)
vnc_url = f"/b/{session_token}"
meeting_data['escalation']['vnc_url'] = vnc_url
meeting_data['escalation']['session_token'] = session_token  # <-- ADD THIS
```

---

## Validation Verdict

| Check | Status |
|-------|--------|
| escalation.ts exports correct functions | PASS |
| All 3 admission files have checkEscalation | PASS |
| utils.ts has callNeedsHumanHelpCallback | PASS |
| schemas.py has NEEDS_HUMAN_HELP + valid transitions | PASS |
| meeting-api handles needs_human_help callback | PASS |
| meeting-api writes browser_session to Redis | PASS |
| orchestrator_utils exposes port 6080 on meeting bots | PASS |
| Dashboard vexa.ts has needs_human_help | PASS |
| Dashboard page.tsx has escalation banner | PASS |
| Dashboard builds clean | **FAIL** |
| VNC button renders correctly | **FAIL** |
| meetingFlow.ts unchanged (no regressions) | PASS |

**Overall: 2 issues must be fixed before the feature is functional.**
