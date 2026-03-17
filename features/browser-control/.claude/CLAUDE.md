# Browser Control Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope

You own the browser control infrastructure: persistent Chromium containers with CDP, PulseAudio, VNC, and cookie management. You enable three things: creating meetings with audio for testing, admitting bots from lobby, and authenticated bot joins for production.

You don't own the transcription pipeline — you provide the meeting + audio that the transcription pipeline consumes.

### Gate (local)

**Phase 1 gate (testing):** Host browser creates a real meeting, plays WAV audio through PulseAudio as mic input, and the Vexa attendance bot on the other side receives transcription segments with non-empty text from that audio.

**Phase 2 gate (production):** User authenticates via VNC URL, cookies persist to DB, bot joins an org-restricted meeting using stored cookies without being rejected.

### Edges

**Sends:**
- Meeting URL → bot-manager (for attendance bot to join)
- Lobby admission click → meeting platform (admits the attendance bot)
- Audio (WAV → PulseAudio → meeting mic) → meeting platform → attendance bot

**Receives:**
- Auth cookies from user (via VNC browser interaction)
- Meeting creation commands from test orchestrator or API

### Counterparts
- **bot-manager** — launches attendance bots against meeting URLs you provide
- **googlemeet agent** — join flow, admission detection on the attendance bot side
- **msteams agent** — same for Teams
- **api-gateway** — POST /auth/browser endpoint (Phase 2)

### Certainty ladder

| Level | Gate |
|-------|------|
| 0 | Not integrated (current — playwright-vnc-poc is separate repo) |
| 30 | Dockerfile copied into vexa, browser builds and starts |
| 50 | CDP creates Google Meet meeting from vexa container |
| 60 | PulseAudio plays WAV as mic input, meeting has audible speech |
| 70 | Attendance bot joins, hears audio, produces transcription segments |
| 80 | Full automated loop: create → play audio → bot joins → host admits → bot transcribes → verify |
| 85 | Same for Teams |
| 90 | Cookie persistence: restart browser, cookies survive, still authenticated |
| 95 | User authenticates via API, cookies in DB, bot joins org-restricted meeting |
| 99 | 10+ automated test cycles across both platforms, zero failures |

## How to test

1. Build host browser: `docker build -f features/browser-control/Dockerfile.host -t vexa-host-browser .`
2. Run it: `docker run -d --name vexa-host -p 6080:6080 -p 9222:9223 --shm-size 2g -v host-cookies:/app/userdata vexa-host-browser`
3. First auth: VNC into localhost:6080, sign in to Google/Teams
4. Create meeting via CDP: `node features/browser-control/create-meeting.js`
5. Play audio: `docker exec vexa-host paplay --device=virtual_mic cache/full-messy/alice.wav`
6. Launch attendance bot: `POST /bots`
7. Admit from lobby: `node features/browser-control/admit-bot.js`
8. Verify: `GET /transcripts` returns segments from the audio played

## Critical findings
Save to `tests/findings.md`.
