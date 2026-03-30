# Video Recording Capability — Research Findings

**Researcher:** video-recording-researcher
**Date:** 2026-03-24
**Status:** VIDEO RECORDING IS ALREADY IMPLEMENTED (85% complete)

---

## Critical Discovery: Implementation Already Exists

Before recommending an approach, the codebase audit revealed that **video recording is already built**. The implementation uses the Xvfb + ffmpeg x11grab approach and covers:

| Component | File | Status |
|-----------|------|--------|
| VideoRecordingService | `services/vexa-bot/core/src/services/video-recording.ts` | Complete |
| Integration in bot lifecycle | `services/vexa-bot/core/src/index.ts` (lines 56-86, 691-718) | Complete |
| Meeting flow hook | `services/vexa-bot/core/src/platforms/shared/meetingFlow.ts` (line 186) | Complete |
| Audio muxing | `VideoRecordingService.muxAudio()` | Complete |
| Upload to meeting-api | `VideoRecordingService.upload()` | Complete |
| Bot-manager upload endpoint | `services/meeting-api/app/main.py` (upload_recording) | Complete (accepts media_type="video") |
| MediaFile DB model | meeting-api DB | Complete (type="video" supported) |
| Recording config API | `PUT /recording-config` | Complete (capture_modes: ["audio", "video"]) |
| Dashboard VideoPlayer | `services/dashboard/src/components/recording/video-player.tsx` | Built but NOT integrated into meeting page |
| Content-type handling | meeting-api download endpoints | Complete (video/webm, video/mp4 routing) |
| Hardware acceleration | VAAPI + NVENC + software VP9 + software H.264 | Complete |
| BotConfig type | `services/vexa-bot/core/src/types.ts` (line 25) | Complete (captureModes?: string[]) |
| Zoom Native guard | `startVideoRecordingIfNeeded()` | Complete (skips Zoom Native, logs warning) |

### What is NOT done (the 15%)

1. **Dashboard integration** — `VideoPlayer` component exists but is not imported/used in the meeting detail page (`services/dashboard/src/app/meetings/[id]/page.tsx`). The page currently only uses `AudioPlayer`.

2. **Bug: `RecordingService.getStartTime()` does not exist** — `index.ts:702` calls `activeRecordingService.getStartTime()` for audio-video sync delay calculation, but `RecordingService` has no `startTime` field or `getStartTime()` method. This will throw a runtime error during muxing. `VideoRecordingService` correctly has this method. The `RecordingService` needs a `startTime` field set in `start()` and a `getStartTime()` method.

3. **ffmpeg not in runtime Dockerfile** — The build stage installs ffmpeg (`apt-get install -y ffmpeg`), but the runtime stage does NOT. The runtime stage only installs `xvfb`, `pulseaudio`, and `xserver-xephyr`. Since the built app is copied from the base stage (`COPY --from=base /app /app`), ffmpeg is NOT available in the runtime container. **Video recording will fail silently** because `spawn('ffmpeg', ...)` will get ENOENT.

4. **No end-to-end test** — No test validates the full video recording pipeline (start -> stop -> mux -> upload -> download -> playback).

5. **Storage sizing not configured** — MinIO bucket likely has no quota policy for video files, which are 10-100x larger than audio.

---

## Approach Comparison (for reference — decision already made)

| Approach | How it works | Quality | CPU cost | Complexity | Platform coverage |
|----------|-------------|---------|----------|------------|-------------------|
| **ffmpeg x11grab (CHOSEN)** | Captures Xvfb display via X11 protocol | Pixel-perfect, full meeting UI | Low-Medium (VP9 realtime), ~5-15% CPU | Low — single ffmpeg process | All platforms (same Xvfb) |
| MediaRecorder API (browser) | Browser JS records visible tab content | Good, but limited to visible content | Low (browser-managed) | Medium — per-platform JS injection | Per-platform (different DOM) |
| CDP Page.startScreencast | Chrome DevTools Protocol frame capture | Frame-by-frame, lower quality | High (CPU for frame encoding) | High — event-based, need ffmpeg pipe | Chromium-only |
| Playwright context.recordVideo | Playwright's built-in video recording | Good (VP8 webm) | Medium | Very low | All Playwright browsers |

### Why ffmpeg x11grab is the right choice

1. **Platform-uniform**: All three platforms (Google Meet, Teams, Zoom Web) render to the same Xvfb display (:99). One recording mechanism covers all.
2. **Decoupled from browser**: Recording runs as a separate ffmpeg process. If the browser crashes, the video file up to that point is still valid (ffmpeg handles SIGTERM gracefully).
3. **No per-platform code**: Unlike MediaRecorder (which needs JS injection per platform), x11grab needs zero platform-specific code.
4. **Codec flexibility**: VP9 (webm), H.264 (mp4), or hardware-accelerated encoding via VAAPI/NVENC.
5. **Audio muxing**: Post-recording mux with the audio WAV creates a single self-contained file.

### Why NOT the alternatives

- **MediaRecorder API**: Already used for audio. Using it for video would require `getDisplayMedia()` which needs a trusted user gesture and platform-specific UI interaction to grant permission. x11grab avoids this entirely.
- **CDP Page.startScreencast**: Event-based architecture (one frame at a time) is fragile. Quality degrades under load. Requires piping frames into ffmpeg anyway — just a more complex version of what x11grab does natively.
- **Playwright recordVideo**: Uses VP8 only, lower quality. Tied to browser context lifecycle. Less control over encoding parameters.

---

## Codec and Format Analysis

### Current implementation options (from `video-recording.ts`)

| Mode | Env var | Codec | Container | Browser support | File size (1hr, 1080p, 10fps) |
|------|---------|-------|-----------|-----------------|-------------------------------|
| Default | `VIDEO_HWACCEL=none` | VP9 (libvpx-vp9) | webm | Chrome, Firefox, Edge, Safari 14+ | ~225-360 MB |
| H.264 CPU | `ENCODE_H264=true` | H.264 (libx264) | mp4 | Universal (incl. older Safari) | ~300-500 MB |
| VAAPI | `VIDEO_HWACCEL=vaapi` | H.264 (h264_vaapi) | mp4 | Universal | ~300-500 MB |
| NVENC | `VIDEO_HWACCEL=nvenc` | H.264 (h264_nvenc) | mp4 | Universal | ~300-500 MB |

### Recommendation: VP9 (default) is correct for most deployments

- **File size**: VP9 at CRF 35 with realtime deadline produces excellent compression for screen content (static slides, text). Estimated 225-360 MB/hour at 1080p 10fps.
- **Browser playback**: Safari 14+ supports VP9 in webm. Since the dashboard is a modern web app, this is acceptable.
- **CPU usage**: VP9 with `cpu-used 8` and `deadline realtime` uses minimal CPU. The existing settings are well-tuned.
- **Fallback**: H.264 via `ENCODE_H264=true` for deployments needing universal compatibility or hardware acceleration.

### Current ffmpeg settings review

```
VP9: -crf 35 -b:v 0 -deadline realtime -cpu-used 8 -row-mt 1
H.264: -crf 28 -preset ultrafast -tune zerolatency -pix_fmt yuv420p
```

These are appropriate for realtime screen capture. The VP9 CRF 35 is aggressive but fine for meeting UI content. H.264 ultrafast+zerolatency is optimal for low-latency capture.

---

## Storage Impact Analysis

| Content type | Format | Size per hour | Ratio to audio |
|-------------|--------|---------------|----------------|
| Audio only | webm (opus) | ~5-10 MB | 1x |
| Audio only | WAV (16kHz mono) | ~115 MB | ~15x |
| Video (no audio) | webm VP9 1080p 10fps | ~225-360 MB | ~40x |
| Video + audio muxed | webm VP9 + opus | ~230-370 MB | ~45x |
| Video (H.264) | mp4 1080p 10fps | ~300-500 MB | ~60x |

### MinIO implications

- A 1-hour meeting video at VP9 quality is ~300 MB.
- 100 meetings/day = ~30 GB/day of video storage.
- Retention policy needed: auto-delete video after N days? Separate from audio retention?
- Consider: MinIO lifecycle rules or cron job for video expiry.

---

## Bugs Found During Research

### Bug 1: `RecordingService.getStartTime()` missing (CRITICAL)

**File**: `services/vexa-bot/core/src/services/recording.ts`
**Impact**: Audio-video sync will fail at runtime. Line 702 of `index.ts` calls `activeRecordingService.getStartTime()` but the method doesn't exist.

**Fix**: Add a `startTime` field and `getStartTime()` method to `RecordingService`:
```typescript
private startTime: number = 0;

start(): void {
  // ... existing code ...
  this.startTime = Date.now();  // ADD THIS
}

getStartTime(): number {
  return this.startTime;
}
```

### Bug 2: ffmpeg missing from runtime Docker image (CRITICAL)

**File**: `services/vexa-bot/core/Dockerfile`
**Impact**: `VideoRecordingService.start()` spawns ffmpeg, but ffmpeg is only installed in the build stage. The runtime stage doesn't install it.

**Fix**: Add `ffmpeg` to the runtime stage `apt-get install`:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    ffmpeg \           # ADD THIS
    pulseaudio \
    xserver-xephyr \
    && rm -rf /var/lib/apt/lists/*
```

### Bug 3: VideoPlayer not wired into meeting page

**File**: `services/dashboard/src/app/meetings/[id]/page.tsx`
**Impact**: Even if video is recorded and uploaded successfully, the dashboard has no way to display it. The `VideoPlayer` component exists at `components/recording/video-player.tsx` but is never imported.

**Fix**: In the meeting detail page, check if the recording has a video `MediaFile` (type="video"). If so, render `VideoPlayer` instead of (or alongside) `AudioPlayer`. The meeting-api already returns `media_files` with `type` field in the recording metadata.

---

## Implementation Plan (for the executor)

### Phase 1: Fix critical bugs (estimated: 30 min)

1. Add `getStartTime()` to `RecordingService`
2. Add `ffmpeg` to Dockerfile runtime stage
3. Rebuild bot container

### Phase 2: Wire dashboard video playback (estimated: 1 hour)

1. In meeting detail page, check recording metadata for video MediaFile
2. If video exists, render `VideoPlayer` with the video stream URL
3. If only audio exists, render `AudioPlayer` (current behavior)
4. If both exist, show `VideoPlayer` (which has muxed audio) as primary, with `AudioPlayer` as fallback
5. Connect transcript click-to-seek to `VideoPlayer.seekTo()`

### Phase 3: End-to-end test (estimated: 1 hour)

1. Enable video recording: `PUT /recording-config { "capture_modes": ["audio", "video"] }`
2. Start a meeting with a TTS bot
3. Verify video file appears in MinIO after meeting ends
4. Verify video plays in dashboard with audio
5. Verify click-to-seek works on transcript segments

### Phase 4: Storage and ops (estimated: 30 min)

1. Configure MinIO lifecycle policy for video files (e.g., 30-day retention)
2. Add `VIDEO_HWACCEL` and `ENCODE_H264` to PORT-MAP.md / env documentation
3. Add video file size to recording metadata response

---

## Competitor Comparison

| Feature | Vexa (current) | Recall.ai | Otter.ai | tl;dv |
|---------|---------------|-----------|----------|-------|
| Video recording | Built but not wired up | Core feature, GA | Yes | Yes, with AI highlights |
| Video format | VP9 webm / H.264 mp4 | Unknown (API-based) | Proprietary | Unknown |
| Hardware accel | VAAPI, NVENC, CPU | Unknown | N/A (cloud) | N/A (cloud) |
| Audio-video sync | Implemented (mux with delay offset) | Built-in | Built-in | Built-in |
| Video playback in dashboard | Component exists, not integrated | Yes | Yes | Yes |
| Resolution | 1080p (Xvfb native) | Unknown | Unknown | Unknown |
| Frame rate | 10fps (configurable) | Unknown | Unknown | Unknown |

### Key takeaway

Vexa is architecturally ahead on video recording compared to where most meeting bots start. The x11grab approach is the same one used by professional screen recording tools. The implementation is 85% done. The remaining 15% is plumbing (fix bugs, wire dashboard), not architecture.

---

## Code Locations Reference

| What | Where |
|------|-------|
| VideoRecordingService | `services/vexa-bot/core/src/services/video-recording.ts` |
| RecordingService (audio) | `services/vexa-bot/core/src/services/recording.ts` |
| Bot lifecycle integration | `services/vexa-bot/core/src/index.ts:56-86, 691-718` |
| Meeting flow (start trigger) | `services/vexa-bot/core/src/platforms/shared/meetingFlow.ts:186` |
| Bot config type | `services/vexa-bot/core/src/types.ts:25` |
| Bot Dockerfile | `services/vexa-bot/core/Dockerfile` |
| Xvfb setup | `services/vexa-bot/core/entrypoint.sh:9` (1920x1080x24) |
| Bot-manager upload endpoint | `services/meeting-api/app/main.py:2055-2260` |
| Recording config API | `services/meeting-api/app/main.py:2625-2688` |
| Download/stream endpoints | `services/meeting-api/app/main.py:2340-2550` |
| Dashboard VideoPlayer | `services/dashboard/src/components/recording/video-player.tsx` |
| Dashboard AudioPlayer | `services/dashboard/src/components/recording/audio-player.tsx` |
| Meeting detail page | `services/dashboard/src/app/meetings/[id]/page.tsx` |
| Google Meet recording | `services/vexa-bot/core/src/platforms/googlemeet/recording.ts` |

---

## External Sources

- [FFmpeg x11grab optimization](https://vyvee.github.io/screen-recording-ffmpeg.html)
- [VP9 encoding settings (Google)](https://developers.google.com/media/vp9/settings/vod)
- [VP9 bitrate modes](https://developers.google.com/media/vp9/bitrate-modes)
- [Recall.ai meeting bot API](https://docs.recall.ai/docs/receive-a-recording)
- [Recall.ai architecture overview](https://www.recall.ai/blog/how-to-build-a-meeting-bot)
- [Playwright video recording docs](https://playwright.dev/docs/videos)
- [CDP screencast approach](https://medium.com/@anchen.li/how-to-do-video-recording-on-headless-chrome-966e10b1221)
- [NVIDIA NVENC ffmpeg livestream](https://gist.github.com/Brainiarc7/4636a162ef7dc2e8c9c4c1d4ae887c0e)
- [VAAPI hardware encoding](https://gist.github.com/Brainiarc7/95c9338a737aa36d9bb2931bed379219)
- [WebM VP9 screen recording optimization](https://www.lexo.ch/blog/2024/09/webm-screen-recording-optimize-simple-screen-recorder-ssr-for-high-quality-low-size-screencasts/)
