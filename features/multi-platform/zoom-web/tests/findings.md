# Zoom Web — Findings

## Gate verdict: INFRASTRUCTURE READY — bot-manager routes to web path

## Score: 25

## Implementation status (2026-03-24)

PR #181 by jbschooley adds a **complete Zoom web client via Playwright** — the same browser-based approach used for Google Meet and Teams. This is NOT the Zoom SDK path (which requires Marketplace review).

### What PR #181 adds

| Component | File | Lines | Description |
|-----------|------|-------|-------------|
| Join flow | `platforms/zoom/web/join.ts` | 162 | Navigate to Zoom URL, handle name entry, join meeting |
| Admission | `platforms/zoom/web/admission.ts` | 118 | Detect waiting room, admission, rejection |
| Recording | `platforms/zoom/web/recording.ts` | 360 | **Caption-based** like Teams — observes Zoom caption DOM for speaker + text |
| Leave | `platforms/zoom/web/leave.ts` | 74 | Click leave button, handle confirmation dialog |
| Removal | `platforms/zoom/web/removal.ts` | 123 | Detect host removal, meeting end, connection loss |
| Prepare | `platforms/zoom/web/prepare.ts` | 75 | Pre-join setup (mute camera, etc.) |
| Selectors | `platforms/zoom/web/selectors.ts` | 104 | DOM selectors for Zoom web UI |
| Index | `platforms/zoom/web/index.ts` | 29 | Platform strategy exports |
| Video recording | `services/video-recording.ts` | 362 | ffmpeg-based video capture (all platforms) |

### Architecture

Same pattern as Teams:
1. Bot joins via browser (Playwright)
2. Zoom web captions provide speaker attribution (like Teams data-tid selectors)
3. Audio captured from browser
4. Transcription via Whisper (realtime) or post-meeting

### Key dependencies

- Zoom web client accessible without SDK (browser-based, no Marketplace review)
- Captions must be enabled in Zoom meeting settings
- Same caption reliability concerns as Teams (if captions unavailable, fallback?)

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Zoom web join flow | 0 | PR #181 code exists, not merged/tested | 2026-03-24 | Merge PR, test with real Zoom meeting |
| Zoom admission handling | 0 | PR code covers waiting room + rejection | 2026-03-24 | Test waiting room + direct join |
| Zoom caption-based recording | 0 | PR uses DOM caption observation | 2026-03-24 | Test with Zoom captions enabled |
| Zoom speaker attribution | 0 | Caption-driven like Teams | 2026-03-24 | Test with 2+ speakers |
| Zoom leave/removal detection | 0 | PR covers leave + host removal | 2026-03-24 | Test all leave scenarios |
| Video recording (all platforms) | 0 | PR adds ffmpeg-based capture | 2026-03-24 | Test video output quality |
| Post-meeting transcription for Zoom | 0 | Should work via existing pipeline if recording saved | 2026-03-24 | Test POST /meetings/{id}/transcribe on Zoom recording |

## Risks

- Zoom web client may require authentication for some meeting types
- Caption availability depends on meeting host settings
- DOM selectors will drift as Zoom updates their web client
- No fallback if captions unavailable (same gap as Teams)
- Zoom may block browser automation (bot detection)

## Executor validation (2026-03-24)

### Step 1: ZOOM_WEB=true added to docker-compose.yml
Added to bot-manager environment section alongside existing RECORDING_ENABLED=true.

### Step 2: bot-manager restarted and env vars confirmed
```
docker exec vexa-agentic-bot-manager-1 env | grep -E "ZOOM_WEB|RECORDING"
RECORDING_ENABLED=true
ZOOM_WEB=true
```

### Step 3: zoom/web/ compiled code verified in image
```
docker run --rm vexa-bot:dev ls /app/vexa-bot/core/dist/platforms/zoom/web/
admission.js  index.js  join.js  leave.js  prepare.js  recording.js  removal.js  selectors.js
```
All 8 modules present. ffmpeg at /usr/bin/ffmpeg.

### Step 4: API acceptance test — PASS
```
POST http://localhost:8066/bots
{"platform":"zoom","native_meeting_id":"12345678901","meeting_url":"https://zoom.us/j/12345678901",...}

Response: {"id":52,"status":"requested","bot_container_id":"11ce3bddba579dc51b9a4355c39bc3b71750c157229a109e110058dafc825574",...}
```
No SDK credential error. Meeting created successfully.

### Step 5: bot-manager log confirms web path
```
INFO - Received bot request for platform 'zoom' with native ID '12345678901' from user 2
WARNING - Zoom OAuth is not connected for user 2; starting meeting 52 without OBF token.
INFO - ZOOM_WEB=true: using Playwright web client for Zoom (no SDK credentials needed)
```
Critical: last line confirms ZOOM_WEB routing is active.

### What still needs testing
- Real Zoom meeting join (requires actual Zoom meeting URL)
- Caption-based transcription (requires host to enable captions)
- Waiting room handling
- Leave/removal detection

## Path to merge

1. Evaluate PR #181 conflicts with our recent changes
2. Resolve conflicts (orchestrator_utils.py, chat.ts, types.ts)
3. Merge PR
4. Rebuild vexa-bot:dev
5. Test with real Zoom meeting
6. Score moves based on test results
