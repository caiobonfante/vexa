# Bot Escalation Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope

You test bot escalation: when a meeting bot is blocked (CAPTCHA, auth wall, waiting room timeout, unexpected UI), it escalates to the user via VNC instead of failing silently. You verify the full chain — detection, notification, VNC handoff, and resume. You dispatch service agents — you don't write code.

### Gate (local)

Bot joins meeting and hits a blocker → `checkEscalation()` fires → VNC starts on-demand → status callback `needs_human_help` sent → bot-manager updates meeting status + registers VNC session in Redis → dashboard shows escalation banner with VNC link → user resolves via VNC → admission poll detects resolution → bot sends `active` callback → meeting continues normally.

PASS: Escalation triggers within 10s of blocker, VNC accessible via `/b/{token}`, dashboard shows banner, bot resumes after user intervention, meeting completes.
FAIL: Bot times out silently, VNC doesn't start, no notification reaches dashboard, bot doesn't resume after user resolves blocker.

### Edges

| Edge | From | To | What to verify |
|------|------|----|----------------|
| Detection | Platform admission poll | `checkEscalation()` | Returns non-null when blocker detected (timeout approaching or unknown state >10s) |
| VNC start | `startVncStack()` | x11vnc + websockify | Ports 5900/6080 listening within 3s |
| Status callback | `callNeedsHumanHelpCallback()` | bot-manager | HTTP 200, meeting status = `needs_human_help` in DB |
| Redis session | bot-manager | `browser_session:{token}` | Token resolves to container, gateway proxies VNC |
| WebSocket push | `publish_meeting_status_change()` | dashboard | `meeting.status` event with `needs_human_help` + `vnc_url` |
| Resume | admission poll | `callStartupCallback()` | Status transitions `needs_human_help` → `active` after user resolves |

### Counterparts

- **New module:** `services/vexa-bot/core/src/platforms/shared/escalation.ts` (detection + VNC start)
- **Service agents:** `services/bot-manager` (callback handling, Redis session), `services/api-gateway` (VNC proxy via `/b/{token}`), `services/dashboard` (escalation banner)
- **Platform admission:** `zoom/web/admission.ts`, `googlemeet/admission.ts`, `msteams/admission.ts` (each gains `checkEscalation()` call)
- **Schema:** `libs/shared-models/shared_models/schemas.py` (`NEEDS_HUMAN_HELP` status)
- **Related features:** realtime-transcription (bot lifecycle), agentic-runtime (browser sessions, VNC infra)

## How to test

1. Start compose stack, ensure bot container image includes x11vnc + websockify
2. Create a meeting with admission controls (waiting room enabled)
3. Send bot to join — do NOT admit it
4. Watch bot logs for `checkEscalation()` triggering after 80% of timeout
5. Verify VNC: `curl http://<container>:6080` returns noVNC page
6. Verify Redis: `GET browser_session:{token}` returns container info
7. Verify dashboard: WebSocket receives `needs_human_help` status, banner renders
8. Open VNC via `/b/{token}`, admit the bot manually
9. Verify bot logs: admission detected, `active` callback sent
10. Verify meeting continues: recording + transcription proceed normally

## Diagnostic hints

- **Escalation doesn't trigger:** Check `checkEscalation()` is called in the platform's admission poll loop. Verify timeout threshold (80% of `waitingRoomTimeout`).
- **VNC won't start:** Confirm x11vnc and websockify binaries exist in container. Check Xvfb is running on `:99`. Look for port conflicts.
- **Dashboard doesn't show banner:** Check WebSocket connection is open. Verify `meeting.status` event includes `escalation_reason` and `vnc_url` in data payload.
- **Bot doesn't resume:** Admission poll must keep running during escalation. Verify timeout was extended (5 min extension). Check `isAdmitted()` returns true after user intervention.
- **VNC accessible but blank:** Xvfb display mismatch — ensure x11vnc uses `-display :99` matching the bot's Xvfb.

## Critical findings

Save to `tests/findings.md`.
