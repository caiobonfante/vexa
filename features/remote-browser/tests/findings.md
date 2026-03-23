# Remote Browser — Findings

## Gate verdict: SCAFFOLD (PoC proven, not integrated)

## Implementation status (audit 2026-03-23)

Working PoC at `/home/dima/dev/playwright-vnc-poc/`. Feature-level code exists:
- `services/vexa-bot/core/src/browser-session.ts` — persistent browser context, VNC integration, CDP/Playwright, MinIO sync with cache exclusions, Git workspace sync
- `services/dashboard/` — browser session view component, browser button in meeting creation
- `services/api-gateway/` — resolves browser sessions via Redis
- `features/remote-browser/scripts/` — auto-admit.js (gmeet-host-auto.js is at `features/realtime-transcription/scripts/gmeet-host-auto.js`)

Scripts in this feature are actively used by the realtime-transcription collection workflow (`/host-teams-meeting-auto` uses browser sessions).

## Scaffold — 2026-03-18

Feature scaffolded from playwright-vnc-poc. No tests run yet.

### Known from PoC
- Chromium persistent context + VNC + CDP: **working** (tested in playwright-vnc-poc)
- Google/Teams auth via VNC: **working**
- Cookie persistence via Docker volumes: **working**
- CDP connect from outside container: **working** (socat proxy required)
- SingletonLock must be cleaned on restart or Chromium won't start

## Confidence ladder

| Level | Gate | Status |
|-------|------|--------|
| 0 | Not started | |
| 30 | Container builds with VNC packages | Done (PoC) |
| 50 | Browser starts in session mode, VNC accessible via URL | Done (PoC) |
| 60 | CDP connection works via gateway proxy | Not tested |
| 70 | User authenticates via VNC, Save syncs to MinIO | Not tested |
| 80 | Restart browser session, all state restored from MinIO | Not tested |
| 90 | Meeting bot with authenticated=true joins as authenticated user | Not tested |
| 95 | Agent controls browser via CDP, creates files, files persist | Not tested |
| 99 | Full round-trip: auth, save, authenticated meeting bot, transcription works | Not tested |

## Risks
- VNC/CDP routing through api-gateway not verified end-to-end
- MinIO sync reliability untested
- No docs page exists for this feature
