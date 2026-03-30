# Video Recording — Findings

**Feature:** video-recording
**Last updated:** 2026-03-25
**Overall status:** 85% implemented, 2 critical bugs block production use

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| ffmpeg x11grab captures display | 80 | Code complete, architecture validated in research. Not E2E tested (ffmpeg missing from runtime Dockerfile) | 2026-03-25 | Fix Bug 2 (add ffmpeg to runtime stage), run E2E capture test |
| VP9/H.264 codec selection | 80 | Code handles all 4 modes (VP9, H.264 CPU, VAAPI, NVENC) with correct ffmpeg args | 2026-03-25 | E2E test each codec path |
| Audio muxing (itsoffset sync) | 70 | `muxAudio()` implemented with delay offset. `RecordingService.getStartTime()` exists (line 233). Not E2E tested. | 2026-03-25 | E2E test: verify muxed file has synced audio |
| Upload to meeting-api | 80 | Upload endpoint accepts media_type="video", content-type routing works | 2026-03-25 | E2E test: record -> upload -> download -> verify playback |
| Dashboard video playback | 10 | VideoPlayer component exists but is NOT imported in meeting page | 2026-03-25 | Fix Bug 3: wire VideoPlayer into meeting detail page |
| Click-to-seek on transcript | 0 | Not implemented | 2026-03-25 | Depends on dashboard integration (Bug 3) |
| Storage/retention policy | 0 | No MinIO lifecycle rules for video files | 2026-03-25 | Configure retention policy, add monitoring |
| Hardware acceleration (VAAPI) | 50 | Code path exists, untested on real hardware | 2026-03-25 | Test on machine with /dev/dri/renderD128 |
| Hardware acceleration (NVENC) | 50 | Code path exists, untested on real hardware | 2026-03-25 | Test on machine with NVIDIA GPU + nvidia runtime |
| Zoom Native guard | 80 | `startVideoRecordingIfNeeded()` skips Zoom Native and logs warning | 2026-03-25 | Verify log output in Zoom Native session |

## Critical Bugs

1. ~~**RecordingService.getStartTime() missing**~~ — INVALID. Method exists at `recording.ts:233`, `startTime` field at line 19. Validator confirmed 2026-03-25.
2. **ffmpeg not in runtime Dockerfile** — Build stage installs it, runtime stage doesn't. `spawn('ffmpeg')` gets ENOENT. Score impact: all recording (80 -> 0 at runtime).
3. **VideoPlayer not wired in** — Component exists at `components/recording/video-player.tsx`, never imported in meeting page. Score impact: dashboard playback (10).

## Approach Decisions

- **x11grab chosen over MediaRecorder/CDP/Playwright** — platform-uniform, decoupled from browser, no per-platform code needed.
- **VP9 default over H.264** — better compression for screen content (40% smaller files), Safari 14+ support sufficient for modern dashboard.
- **Post-recording mux over live mux** — simpler architecture, audio and video start times may differ, `itsoffset` handles sync.

## Dead Ends

(None yet — feature has not been through iteration cycles)

## Next Steps

1. Fix Bug 2 (ffmpeg in Dockerfile) — unblocks E2E testing
2. Fix Bug 3 (wire VideoPlayer) — unblocks dashboard playback
4. Run first E2E test: enable video capture, join meeting, verify muxed file plays correctly
5. Configure MinIO retention policy for video files
