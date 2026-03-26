# Zoom Web Client Audio Architecture Research

Date: 2026-03-25 (updated with live evidence from bot 60)
Context: Task #18 — Compare Zoom audio capture with GMeet/Teams, determine per-speaker feasibility

## Executive Summary

**CORRECTION:** Zoom's web client DOES provide per-speaker audio via separate `<audio>` elements — the same architecture as Google Meet. Live evidence from bot 60 shows 3 separate media elements with individual MediaStream tracks, and the existing `startPerSpeakerAudioCapture()` pipeline successfully captures and transcribes per-speaker audio.

The Zoom web recording code (`recording.ts`) uses PulseAudio mixed capture as a PARALLEL path, not the only path. The per-speaker ScriptProcessor pipeline (`index.ts:1689-1855`) runs alongside it and successfully discovers Zoom's `<audio>` elements.

The remaining gap is `speaker-identity.ts` — `resolveSpeakerName()` doesn't handle zoom, so per-speaker streams work but speaker names aren't resolved.

## Live Evidence: Bot 60 (2026-03-25)

From the team-lead's direct observation of bot 60 in a live Zoom meeting:

```
Found 3 active media elements with audio tracks
Element 1: paused=false, readyState=4, tracks=1
Element 2: paused=false, readyState=4, tracks=1
Element 3: paused=false, readyState=4, tracks=1

[PerSpeaker] Stream 0 started (track: d08ef647)
[PerSpeaker] Stream 1 started (track: 14461004)
[PerSpeaker] Stream 2 started (track: 42332bb6)

[NEW SPEAKER] Track 0 — first audio received
[CONFIRMED] Dmitriy Grankin | "Tak, nu chto u nas Zoom?"
```

This proves:
1. Zoom web client creates separate `<audio>` elements per participant (same as GMeet)
2. Each element has its own MediaStream with a unique audio track
3. `startPerSpeakerAudioCapture()` discovers them and creates ScriptProcessor pipelines
4. Transcription produces confirmed segments with correct text
5. Speaker name "Dmitriy Grankin" was resolved (likely from DOM polling, not `resolveSpeakerName()`)

## Platform Comparison (Corrected)

### Google Meet — Per-Speaker via DOM MediaStreams
1. Each remote participant gets a separate `<audio>` element in the DOM
2. Each element has `srcObject = MediaStream` with an individual audio track
3. `startPerSpeakerAudioCapture()` discovers these elements
4. For each: `AudioContext` + `ScriptProcessorNode` pipeline
5. Speaker identity via `resolveSpeakerName()` DOM scraping

### MS Teams — Per-Speaker via RTCPeerConnection Hook
1. RTCPeerConnection `ontrack` intercepted via `addInitScript`
2. Hidden `<audio>` elements created from remote tracks
3. Same `startPerSpeakerAudioCapture()` pipeline as GMeet
4. Speaker identity via `resolveSpeakerName()` DOM roster scraping

### Zoom — Per-Speaker via DOM MediaStreams (SAME AS GMEET)
1. **Each remote participant gets a separate `<audio>` element** — confirmed by bot 60
2. Each element has `srcObject = MediaStream` with individual audio track
3. `startPerSpeakerAudioCapture()` discovers them — **already working**
4. Same ScriptProcessor pipeline as GMeet — **already producing transcription**
5. **ADDITIONALLY** runs PulseAudio mixed capture (`recording.ts`) as parallel path with DOM-based speaker polling

### Architecture Summary

| Feature | GMeet | Teams | Zoom |
|---------|-------|-------|------|
| Per-speaker `<audio>` elements | Native | Created via RTCPeerConnection hook | Native |
| ScriptProcessor pipeline | Yes | Yes | Yes (working) |
| PulseAudio capture | No | No | Yes (parallel path) |
| `resolveSpeakerName()` | Implemented | Implemented | **NOT IMPLEMENTED** |
| DOM speaker polling | No | No | Yes (250ms polling) |

## Remaining Gap: Speaker Name Resolution

The only missing piece for full Zoom per-speaker transcription is `resolveSpeakerName()` in `speaker-identity.ts:332`. Currently returns empty string for `zoom`.

### What's needed
A Zoom-specific implementation that maps track labels (e.g., `d08ef647`) to participant names by scraping the Zoom web client DOM. The approach should mirror GMeet's voting system:
1. Query Zoom DOM for participant tiles and their names (`.video-avatar__avatar-footer`)
2. Correlate active speaker CSS (`.speaker-active-container__video-frame`) with audio activity on tracks
3. Vote on track→name mappings, lock after threshold

### Why DOM polling alone isn't enough
The DOM polling in `recording.ts` detects WHO is speaking via CSS selectors, but it feeds into the WhisperLive mixed-audio path. The per-speaker pipeline needs `resolveSpeakerName()` to label each ScriptProcessor stream with the correct participant name.

## Code Locations

| Component | File | Status |
|-----------|------|--------|
| Per-speaker audio capture | `index.ts:1689-1855` | Working for Zoom |
| Zoom mixed capture (parallel) | `platforms/zoom/web/recording.ts` | Working |
| Speaker identity | `services/speaker-identity.ts:320-343` | Needs Zoom handler |
| DOM speaker polling | `platforms/zoom/web/recording.ts:296-348` | Working (feeds WhisperLive) |
| Zoom selectors | `platforms/zoom/web/selectors.ts` | Complete |

## Previous Incorrect Assessment

My initial research (before bot 60 evidence) incorrectly concluded with 85% confidence that Zoom delivers a single mixed audio stream. This was wrong because:
1. I assumed PulseAudio capture was the only audio path — it's actually a parallel path
2. I didn't account for the shared `startPerSpeakerAudioCapture()` running on all platforms
3. Bot 57's container was auto-removed before I could inspect the DOM
4. I incorrectly inferred from the PulseAudio choice that per-speaker wasn't available

The lesson: verify assumptions with live evidence before declaring high-confidence conclusions.

## Recommendations

1. **Immediate:** Implement `resolveSpeakerName()` for zoom platform — map Zoom DOM participant tiles to audio track labels using the same voting pattern as GMeet
2. **Consider:** Whether the PulseAudio parallel path in `recording.ts` is still needed, or if per-speaker capture is sufficient (it may serve as a fallback)
3. **No need for:** RTCPeerConnection hooks (unlike Teams), RTMS SDK, or client-side diarization — the native approach works
