# Video Recording

> **Status: 85% implemented** — Core pipeline built and working. Three bugs block production use.
> **Approach:** ffmpeg x11grab on Xvfb display. Platform-uniform (Meet, Teams, Zoom Web all use same Xvfb).
> **Not done:** Dashboard integration, RecordingService.getStartTime() bug, ffmpeg missing from runtime Dockerfile.

## Why

Video recording is **table-stakes** for meeting AI products. Every competitor ships it (Otter.ai, Fireflies, tl;dv, Recall.ai, MeetGeek). Without it, Vexa captures audio but loses slides, screen shares, visual reactions, and chat — content that users expect in meeting recordings.

The x11grab approach is the right architectural choice:

| Advantage | Detail |
|-----------|--------|
| **Platform-uniform** | All platforms render to the same Xvfb display (:99). One recording mechanism covers Meet, Teams, Zoom Web. |
| **Decoupled from browser** | ffmpeg runs as a separate process. Browser crash = video up to that point is still valid. |
| **No per-platform code** | Unlike MediaRecorder (needs JS injection per platform), x11grab needs zero platform-specific code. |
| **Codec flexibility** | VP9 (webm), H.264 (mp4), or hardware-accelerated via VAAPI/NVENC. |
| **Self-hosted** | Video stays on your infrastructure. No third-party cloud processing. |

## What

### Architecture

```
Xvfb display (:99, 1920x1080x24)
     |
     v
ffmpeg x11grab (10fps, VP9/H.264)
     |                                RecordingService (audio)
     v                                       |
  video file (/tmp/video_*.webm)             v
     |                               audio file (/tmp/*.wav)
     |                                       |
     +------------- muxAudio() -------------+
                       |
                       v
              muxed file (video + audio, synced via itsoffset)
                       |
                       v
              upload() → meeting-api (POST /internal/recordings/upload, media_type="video")
                       |
                       v
              MinIO (vexa-recordings bucket)
                       |
                       v
              Dashboard VideoPlayer (component exists, not wired in)
```

### Components

| Component | File | Status |
|-----------|------|--------|
| VideoRecordingService | `services/vexa-bot/core/src/services/video-recording.ts` | Complete |
| Bot lifecycle integration | `services/vexa-bot/core/src/index.ts` (lines 56-86, 691-718) | Complete |
| Meeting flow hook | `services/vexa-bot/core/src/platforms/shared/meetingFlow.ts` (line 186) | Complete |
| Audio muxing | `VideoRecordingService.muxAudio()` | Complete |
| Upload to meeting-api | `VideoRecordingService.upload()` | Complete |
| Meeting-api upload endpoint | `services/meeting-api/meeting_api/recordings.py` (`POST /internal/recordings/upload`) | Complete |
| MediaFile DB model | meeting-api DB (type="video" supported) | Complete |
| Recording config API | Per-user recording_config in user.data (set via meeting creation) | Complete |
| Content-type handling | meeting-api download endpoints (video/webm, video/mp4 routing) | Complete |
| Hardware acceleration | VAAPI + NVENC + software VP9 + software H.264 | Complete |
| BotConfig type | `services/vexa-bot/core/src/types.ts` (line 25, captureModes?: string[]) | Complete |
| Zoom Native guard | `startVideoRecordingIfNeeded()` — skips Zoom Native, logs warning | Complete |
| Dashboard VideoPlayer | `services/dashboard/src/components/recording/video-player.tsx` | Built, NOT integrated |

### Codec Options

| Mode | Env var | Codec | Container | Browser support | Size (1hr, 1080p, 10fps) |
|------|---------|-------|-----------|-----------------|---------------------------|
| Default | `VIDEO_HWACCEL=none` | VP9 (libvpx-vp9) | webm | Chrome, Firefox, Edge, Safari 14+ | ~225-360 MB |
| H.264 CPU | `ENCODE_H264=true` | H.264 (libx264) | mp4 | Universal | ~300-500 MB |
| VAAPI | `VIDEO_HWACCEL=vaapi` | H.264 (h264_vaapi) | mp4 | Universal | ~300-500 MB |
| NVENC | `VIDEO_HWACCEL=nvenc` | H.264 (h264_nvenc) | mp4 | Universal | ~300-500 MB |

VP9 (default) is correct for most deployments — best compression for screen content, CRF 35 with realtime deadline.

### ffmpeg Settings

```
VP9:   -crf 35 -b:v 0 -deadline realtime -cpu-used 8 -row-mt 1
H.264: -crf 28 -preset ultrafast -tune zerolatency -pix_fmt yuv420p
```

### MVP Ladder

| Level | Milestone | Status | Blocker |
|-------|-----------|--------|---------|
| MVP0 | VideoRecordingService captures Xvfb display to file | Done | -- |
| MVP1 | Audio muxing with sync offset | Done | -- |
| MVP2 | Upload to meeting-api, stored in MinIO | Done | ffmpeg missing from runtime Dockerfile (Bug 2) |
| MVP3 | Dashboard plays video with synced audio | Not started | VideoPlayer not wired in (Bug 3), RecordingService.getStartTime() missing (Bug 1) |
| MVP4 | Click-to-seek: transcript segment click jumps video to correct position | Not started | Depends on MVP3 |

### Known Bugs

**Bug 1: `RecordingService.getStartTime()` does not exist (CRITICAL)**
- **File:** `services/vexa-bot/core/src/services/recording.ts`
- **Impact:** `index.ts:702` calls `activeRecordingService.getStartTime()` for audio-video sync delay calculation. `RecordingService` has no `startTime` field or `getStartTime()` method. Will throw at runtime during muxing.
- **Fix:** Add `startTime` field set in `start()` and `getStartTime()` method to `RecordingService`.

**Bug 2: ffmpeg not in runtime Dockerfile (CRITICAL)**
- **File:** `services/vexa-bot/core/Dockerfile`
- **Impact:** Build stage installs ffmpeg but runtime stage does not. `spawn('ffmpeg', ...)` will get ENOENT. Video recording fails silently.
- **Fix:** Add `ffmpeg` to runtime stage `apt-get install`.

**Bug 3: VideoPlayer not wired into meeting page**
- **File:** `services/dashboard/src/app/meetings/[id]/page.tsx`
- **Impact:** Video records and uploads successfully but dashboard has no way to display it. `VideoPlayer` component exists at `components/recording/video-player.tsx` but is never imported.
- **Fix:** Check recording metadata for video MediaFile (type="video"). Render `VideoPlayer` if video exists, `AudioPlayer` as fallback.

### Storage Impact

| Content | Format | Size/hour | Ratio to audio |
|---------|--------|-----------|----------------|
| Audio only | webm (opus) | ~5-10 MB | 1x |
| Video (no audio) | webm VP9 1080p 10fps | ~225-360 MB | ~40x |
| Video + audio muxed | webm VP9 + opus | ~230-370 MB | ~45x |
| Video (H.264) | mp4 1080p 10fps | ~300-500 MB | ~60x |

100 meetings/day = ~30 GB/day video storage. Retention policy needed (MinIO lifecycle rules).

## How

### Implementation Status: 85%

All core recording, encoding, muxing, and upload logic is built and integrated into the bot lifecycle. What remains is plumbing (fix 3 bugs, wire dashboard).

### Approach Comparison (decision already made)

| Approach | Chosen? | Why / Why not |
|----------|---------|---------------|
| **ffmpeg x11grab** | Yes | Platform-uniform, decoupled from browser, no per-platform code |
| MediaRecorder API (browser) | No | Needs `getDisplayMedia()` + trusted user gesture per platform |
| CDP Page.startScreencast | No | Event-based, fragile under load, needs ffmpeg pipe anyway |
| Playwright recordVideo | No | VP8 only, tied to browser context lifecycle |

### Test Procedure

1. Enable video recording:
   ```bash
   curl -X PUT http://localhost:8055/recording-config \
     -H "Content-Type: application/json" \
     -d '{"capture_modes": ["audio", "video"]}'
   ```
2. Start a meeting, send a bot
3. After meeting ends, verify video file in MinIO
4. Download and verify playback with muxed audio
5. (After Bug 3 fix) Verify dashboard VideoPlayer renders and click-to-seek works

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DISPLAY` | `:99` | Xvfb display to capture |
| `VIDEO_HWACCEL` | `none` | Hardware acceleration mode: `none`, `vaapi`, `nvenc` |
| `ENCODE_H264` | `false` | Use H.264 (libx264) instead of VP9 when `VIDEO_HWACCEL=none` |

### Competitor Comparison

| Feature | Vexa | Recall.ai | Otter.ai | tl;dv |
|---------|------|-----------|----------|-------|
| Video recording | 85% built, not production | Core feature, GA | Yes | Yes, with AI highlights |
| Video format | VP9 webm / H.264 mp4 | Unknown (API-based) | Proprietary | Unknown |
| Hardware accel | VAAPI, NVENC, CPU | Unknown | N/A (cloud) | N/A (cloud) |
| Audio-video sync | Implemented (mux with delay offset) | Built-in | Built-in | Built-in |
| Dashboard playback | Component exists, not integrated | Yes | Yes | Yes |
| Self-hosted | Yes | No (SaaS) | No (SaaS) | No (SaaS) |
| Resolution | 1080p (Xvfb native) | Unknown | Unknown | Unknown |

### Code Locations

| What | Where |
|------|-------|
| VideoRecordingService | `services/vexa-bot/core/src/services/video-recording.ts` |
| RecordingService (audio) | `services/vexa-bot/core/src/services/recording.ts` |
| Bot lifecycle integration | `services/vexa-bot/core/src/index.ts:56-86, 691-718` |
| Meeting flow (start trigger) | `services/vexa-bot/core/src/platforms/shared/meetingFlow.ts:186` |
| Bot config type | `services/vexa-bot/core/src/types.ts:25` |
| Bot Dockerfile | `services/vexa-bot/core/Dockerfile` |
| Xvfb setup | `services/vexa-bot/core/entrypoint.sh:9` (1920x1080x24) |
| Meeting-api upload endpoint | `services/meeting-api/meeting_api/recordings.py` |
| Recording config API | Per-user recording_config in user.data |
| Dashboard VideoPlayer | `services/dashboard/src/components/recording/video-player.tsx` |
| Dashboard meeting page | `services/dashboard/src/app/meetings/[id]/page.tsx` |

## Development Notes

### Diagnostic hints

- **ffmpeg ENOENT:** ffmpeg not installed in runtime Dockerfile stage. Check `services/vexa-bot/core/Dockerfile` runtime apt-get.
- **getStartTime() throws:** RecordingService missing startTime field/method. Check `services/vexa-bot/core/src/services/recording.ts`.
- **Video file 0 bytes:** Xvfb not running on :99 or DISPLAY env not set. Check `docker exec vexa-bot env | grep DISPLAY`.
- **No VideoPlayer in dashboard:** Component exists at `components/recording/video-player.tsx` but not imported in `meetings/[id]/page.tsx`.
- **Audio-video desync:** muxAudio() itsoffset calculation wrong -- compare RecordingService.getStartTime() vs VideoRecordingService.startTime.

### Edge verification

| Edge | From | To | What to verify |
|------|------|----|---------------|
| Display capture | Xvfb (:99) | ffmpeg x11grab | ffmpeg process spawns, no ENOENT, output file grows |
| Audio sync | RecordingService.getStartTime() | VideoRecordingService.muxAudio() | startTime exists, itsoffset applied correctly |
| Upload | VideoRecordingService.upload() | meeting-api POST /internal/recordings/upload | HTTP 200, media_type="video" stored |
| Storage | meeting-api | MinIO (vexa-recordings) | Video file retrievable, correct content-type (video/webm or video/mp4) |
| Dashboard | GET /recordings | VideoPlayer component | Component renders, video plays, click-to-seek jumps correctly |
| Config | PUT /recording-config | BotConfig.captureModes | Bot receives ["audio", "video"] and starts video recording |
