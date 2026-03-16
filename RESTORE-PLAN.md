# Vexa Bot Restore Plan

## WHY

The `latest` branch accumulated ~12 commits (Mar 17-18) that broke real-time transcription on both MS Teams and Google Meet. The commits mixed good bug fixes with breaking changes (unconditional video block patching RTCPeerConnection, ring buffer temporal dead zones, camera removal that gutted needed code). Repeated "fix the fix" commits made the state worse. Four independent feature branches all froze at `30d0e30` — confirming it was the last known good state.

## WHAT

Restore vexa-bot to a validated working state, then selectively re-apply improvements.

**"Good state" definition — slim silent transcription bot:**
- No TTS, no speaking, no camera (voice agent features OFF by default)
- Muted outgoing audio (browser feeds `/dev/null`)
- Blocks incoming video (saves CPU)
- Joins MS Teams bulletproof
- Joins Google Meet bulletproof
- Per-speaker real-time transcription works on both platforms
- Bot is invisible/silent in the meeting

**Base commit:** `30d0e30` (Mar 15 — "Implement Teams per-speaker transcription via DOM-routed single audio stream")

## HOW

### Phase 1: Validate baseline (CURRENT)
- [x] Clone repo to `/home/dima/dev/vexa-restore`
- [x] Create branch `fix/restore-working-bot` from `30d0e30`
- [x] Confirm bot is slim/silent by default (code audit: PASS)
- [ ] Build bot from `30d0e30`
- [ ] Test with real Google Meet — confirm transcription works
- [ ] Test with real MS Teams — confirm transcription works
- [ ] Both pass → baseline validated

### Phase 2: Cherry-pick good stuff (one at a time, validate each)

Each cherry-pick gets a real meeting test before moving to the next.

**Candidate 1: `c7acda6` — bot audio pipeline fixes (PARTIAL)**
Good parts to take:
- GC prevention for AudioContext/ScriptProcessor nodes (critical — prevents silent audio)
- AudioContext `.resume()` for autoplay policy
- Manual loop replacing `Math.max(...spread)` (prevents stack overflow on large buffers)
- `browser.ts`: remove `!track.muted` filter (fixes Teams audio capture)
- `vad.ts`: add fallback paths for silero model
- `admission.ts`: trust admission indicators, remove lobby false-positive
- `selectors.ts`: remove false-positive waiting room selectors
- `recording.ts` (Google Meet): exclude bot's own tile from participant count

Skip:
- `recording.ts` (Teams): ring buffer — confirmed breaking speaker detection

**Candidate 2: `93cecc4` — TTS plumbing (additive)**
- `docker.ts`: add `ttsEnabled` field
- `types.ts`: add `ttsEnabled` flag
- Error logging improvements in `index.ts`, `recording.ts`, `meetingFlow.ts`
- `screen-content.ts`: RTCPeerConnection diagnostics

**Candidate 3: New capability flags**
- `types.ts`: `videoReceiveEnabled`, `cameraEnabled` (from `dbb2616`/`59be971`)
- `docker.ts`: Zod schema for new flags
- `constans.ts`: rename to `needsAudio` parameter

**Candidate 4: Entrypoint improvements**
- `entrypoint.sh`: `pactl set-sink-mute tts_sink 1` at startup
- `tts-playback.ts`: unmute/mute around playback, delays to prevent clipping

**Candidate 5: New features from Mar 18**
- `browser-session.ts`: remote browser feature
- Bot-manager / API gateway changes
- Skills and meeting-host tooling

### Phase 3: PR and merge
- [ ] All cherry-picks validated with real meetings
- [ ] Create PR to `latest` branch
- [ ] Document what was kept, what was dropped, and why

## Decision log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-03-18 | Base = `30d0e30` | 4 branches froze here, confirmed working |
| 2026-03-18 | Skip ring buffer from `c7acda6` | `ab2d814` confirmed it breaks Teams speaker detection |
| | | |
