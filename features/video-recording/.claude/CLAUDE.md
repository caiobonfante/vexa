# Video Recording Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope

You test the video recording pipeline: ffmpeg x11grab captures the Xvfb display during a meeting, muxes with audio, uploads to MinIO via bot-manager, and plays back in the dashboard with click-to-seek.

### Gate (local)

Bot joins meeting with `capture_modes: ["audio", "video"]` → ffmpeg captures Xvfb display → meeting ends → video muxed with audio (sync offset) → uploaded to MinIO → GET /recordings returns video file → dashboard VideoPlayer renders and click-to-seek works.

**PASS:** Video file in MinIO with muxed audio, playback works in dashboard, click-to-seek offset < 3s.
**FAIL:** ffmpeg fails to start, no video in MinIO, audio-video desync > 2s, or dashboard doesn't render video.

### Edges

| Edge | From | To | What to verify |
|------|------|----|---------------|
| Display capture | Xvfb (:99) | ffmpeg x11grab | ffmpeg process spawns, no ENOENT, output file grows |
| Audio sync | RecordingService.getStartTime() | VideoRecordingService.muxAudio() | startTime exists, itsoffset applied correctly |
| Upload | VideoRecordingService.upload() | bot-manager POST /upload | HTTP 200, media_type="video" stored |
| Storage | bot-manager | MinIO (vexa-recordings) | Video file retrievable, correct content-type (video/webm or video/mp4) |
| Dashboard | GET /recordings | VideoPlayer component | Component renders, video plays, click-to-seek jumps correctly |
| Config | PUT /recording-config | BotConfig.captureModes | Bot receives ["audio", "video"] and starts video recording |

### Counterparts

- **Service agents:** `services/vexa-bot/core` (VideoRecordingService, RecordingService), `services/bot-manager` (upload endpoint, recording-config), `services/dashboard` (VideoPlayer)
- **Related features:** post-meeting-transcription (shares recording infrastructure), realtime-transcription (bot lifecycle)

## How to test

1. Ensure compose stack is running and ffmpeg is installed in the bot container:
   `docker exec vexa-bot which ffmpeg` — must return a path
2. Enable video recording:
   ```bash
   curl -X PUT http://localhost:8055/recording-config \
     -H "Content-Type: application/json" \
     -d '{"capture_modes": ["audio", "video"]}'
   ```
3. Start a meeting and send a bot (any platform — x11grab is platform-uniform)
4. During meeting, verify ffmpeg is running: `docker exec vexa-bot ps aux | grep ffmpeg`
5. End the meeting — watch bot logs for muxAudio() and upload() completion
6. Verify video in MinIO: check bot-manager logs for successful upload with media_type="video"
7. Download video and verify: has video track, has audio track, audio-video sync < 2s
8. (After dashboard wiring) Open meeting page — VideoPlayer should render, click transcript segment to seek

## Diagnostic hints

- **ffmpeg ENOENT:** ffmpeg not installed in runtime Dockerfile stage. Check `services/vexa-bot/core/Dockerfile` runtime apt-get.
- **getStartTime() throws:** RecordingService missing startTime field/method. Check `services/vexa-bot/core/src/services/recording.ts`.
- **Video file 0 bytes:** Xvfb not running on :99 or DISPLAY env not set. Check `docker exec vexa-bot env | grep DISPLAY`.
- **No VideoPlayer in dashboard:** Component exists at `components/recording/video-player.tsx` but not imported in `meetings/[id]/page.tsx`.
- **Audio-video desync:** muxAudio() itsoffset calculation wrong — compare RecordingService.getStartTime() vs VideoRecordingService.startTime.

See [README.md](../README.md) for architecture, MVPs, and knowledge.

## Critical findings

Save to `tests/findings.md`.
