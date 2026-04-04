# Mission: /host-gmeet-meeting-auto command

## Goal
Create a working `/host-gmeet-meeting-auto` slash command that delivers a Google Meet URL with auto-admit in under 1 minute. Any bot must be able to join and be admitted automatically.

## Current State
- Teams equivalent exists: `.claude/commands/host-teams-meeting-auto.md` — works, tested 2026-03-21
- Google Meet host script exists: `features/realtime-transcription/scripts/gmeet-host-auto.js`
- Unified auto-admit script exists: `features/realtime-transcription/scripts/auto-admit.js` (supports both GMeet and Teams)
- Two browser session containers already running: `meeting-5-*` (CDP :33052), `meeting-7-*` (CDP :33053)
- **BLOCKER**: `ADMIN_API_TOKEN` env var is empty in admin-api container — all admin API calls return "Admin authentication is not configured"

## Architecture
- Services route through API Gateway at `localhost:8056`
  - `/admin/*` → admin-api (port 8001 internal)
  - `/bots` → meeting-api (port 8080 internal)
- Browser sessions are Docker containers with CDP exposed, SSH available
- CDP is proxied by meeting-api at `/b/{session_token}/cdp`
- Or accessible directly via mapped host port (e.g., `localhost:33052`)

## Definition of Done
1. `ADMIN_API_TOKEN` is set so admin-api accepts requests
2. Command file at `.claude/commands/host-gmeet-meeting-auto.md` has correct API endpoints matching the current infrastructure
3. Running `/host-gmeet-meeting-auto` creates a Google Meet meeting via browser automation
4. Auto-admit is running and confirmed working (log shows activity)
5. A test bot can join the meeting URL and gets admitted
6. Total time from command invocation to "meeting ready" < 1 minute

## Key Files
- `.claude/commands/host-gmeet-meeting-auto.md` — the command (already drafted, needs fixes)
- `features/realtime-transcription/scripts/gmeet-host-auto.js` — creates + joins meeting
- `features/realtime-transcription/scripts/auto-admit.js` — admits lobby participants
- `deploy/compose/docker-compose.yml` — service definitions
- `services/api-gateway/main.py` — request routing
