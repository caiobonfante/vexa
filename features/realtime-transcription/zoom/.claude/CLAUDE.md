# Zoom Realtime Transcription Agent

> Shared protocol: [agents.md](../../../../.claude/agents.md) -- phases, diagnostics, logging, gate rules

## Scope

You test the Zoom browser-based per-speaker audio capture and transcription pipeline: bot joins a Zoom meeting via the web client, ScriptProcessor per element captures audio (GMeet pattern — separate `<audio>` per participant), speaker identity locks via voting, TranscriptionClient sends WAV to transcription-service, confirmed segments publish to Redis, collector persists to Postgres.

### Gate (local)

Bot joins Zoom meeting via browser -> audio capture starts via ScriptProcessor -> non-silent audio (amplitude > 0.005) -> speakers locked -> transcription returns non-empty text -> segments in Redis with correct speaker names.

**PASS:** Bot joins via browser, media elements found with non-silent audio, speakers locked, transcription returns non-empty text, segments in Redis and Postgres with correct names.
**FAIL:** No media elements, audio silent, speaker lock fails, transcription empty, or segments missing.

### Edges

| Edge | From | To | What to verify |
|------|------|----|---------------|
| Audio channel join | `prepareZoomWebMeeting()` | Zoom audio subsystem | Bot joins computer audio (not video-only) |
| Audio capture | Browser ScriptProcessor | `handlePerSpeakerAudioData()` | Non-silent audio arrives (max amplitude > 0.005) |
| Speaker identity | `queryZoomActiveSpeaker()` + `traverseZoomDOM()` | `recordTrackVote()` | Active speaker correlated with audio track, lock at 2 votes |
| Transcription | `TranscriptionClient.transcribe()` | transcription-service | HTTP 200, response has non-empty `text` field |
| Publish | `SegmentPublisher` | Redis `transcription_segments` | XADD succeeds, segment has speaker name |
| Consume | Redis stream | transcription-collector | Segment appears in Redis Hash for the meeting |
| Persist | Background task | Postgres | After 30s, segment in `transcription_segments` table |

### Counterparts

- **Parent:** `features/realtime-transcription` (orchestrator)
- **Siblings:** `features/realtime-transcription/google-meet` (reference — same audio pattern), `features/realtime-transcription/ms-teams`
- **Service agents:** `services/bot-manager` (bot lifecycle), `services/transcription-collector` (segment persistence), `services/api-gateway` (delivery)

## How to test

1. Ensure compose stack is running (`make all` from `deploy/compose/`)
2. Create a Zoom meeting (or use an existing meeting URL)
3. POST to bot-manager to create a bot targeting the Zoom meeting URL
4. Watch bot logs for:
   - `prepareZoomWebMeeting` -> "Joined with Computer Audio"
   - `[PerSpeaker] Found N media elements with audio`
   - Non-silent amplitude (max > 0.005)
   - `[SpeakerIdentity] Track N -> "{name}" LOCKED PERMANENTLY`
   - TranscriptionClient HTTP 200 responses with non-empty text
5. Check Redis: `XLEN transcription_segments`, `HGETALL meeting:{id}:segments`
6. Check REST: `GET /transcripts/{meeting_id}` — verify speakers present

Testing currently requires live meetings (no auto-admit yet). MVP3 adds TTS bot testing.

## Diagnostic hints

- **Audio elements found but silent:** Bot didn't join audio channel. Check `prepareZoomWebMeeting()` logs for "Joined with Computer Audio". Root cause: recorder bot clicks "Continue without microphone and camera" bypassing audio.
- **Speaker names empty:** `queryZoomActiveSpeaker()` returns null — verify `.speaker-active-container__video-frame` exists in DOM. Check `isMostRecentlyActiveTrack()` gating.
- **TTS bots ejected (~4s):** Check `removal.ts` logs — likely false-positive from `framenavigated` during Zoom post-join redirect. Also: no auto-admit for waiting room yet.
- **PulseAudio captures silence:** Expected. Chrome doesn't route Zoom WebRTC through PulseAudio. Per-speaker ScriptProcessor is the only working path.
- **Duplicate segments:** Both PulseAudio+WhisperLive and ScriptProcessor+TranscriptionClient run simultaneously. Per-speaker is primary.

## References

- **Full architecture, MVPs, code locations, dead ends:** [README.md](../README.md)
- **Research:** [audio-architecture](../tests/audio-architecture-research.md), [speaker-research](../tests/speaker-research.md)

## Critical findings

Save to `tests/findings.md`.
