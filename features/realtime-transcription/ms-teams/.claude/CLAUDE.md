# MS Teams Realtime Transcription Agent

> Shared protocol: [agents.md](../../../../.claude/agents.md) -- phases, diagnostics, logging, gate rules

## Scope

You test the MS Teams per-speaker transcription pipeline: bot joins a Teams meeting, hooks the single mixed audio stream, enables live captions, and routes audio using caption-driven speaker detection (primary) with DOM blue squares as fallback. A 5s ring buffer provides lookback for retroactive speaker attribution. Transcribes via TranscriptionClient and publishes confirmed segments to Redis.

### Gate (local)

Bot joins live Teams meeting -> captions enabled -> audio routed per speaker via caption boundaries (or DOM fallback) -> TranscriptionClient logs show HTTP 200 with non-empty text -> segments in Redis with correct speaker names.

**PASS:** Audio routed to correct speakers, transcription returns non-empty text, segments in Redis with correct names.
**FAIL:** Audio not captured, wrong speaker routing, transcription empty, or segments missing.

### Edges

| Edge | From | To | What to verify |
|------|------|----|---------------|
| Caption enable | `captions.ts` (post-join) | Teams UI menu clicks | Captions wrapper appears in DOM |
| Caption observer | MutationObserver on `closed-caption-renderer-wrapper` | `lastCaptionSpeaker` + ring buffer flush | Speaker changes detected, lookback audio flushed |
| Audio hook | Browser ScriptProcessor (single stream) | Ring buffer + `handleTeamsAudioData(name, data)` | Non-silent audio stored in ring buffer, routed to caption/DOM speaker |
| Caption data | Browser `__vexaTeamsCaptionData()` | `handleTeamsCaptionData()` | Caption text + speaker logged |
| Speaker detection (fallback) | MutationObserver on `voice-level-stream-outline` | `speakingStates` map | State transitions fire, `vdi-frame-occlusion` detected |
| Transcription | `TranscriptionClient.transcribe()` | transcription-service | HTTP 200, non-empty text |
| Publish | `SegmentPublisher` | Redis `transcription_segments` | XADD succeeds, includes source/caption fields |

### Counterparts

- **Parent:** `features/realtime-transcription` (orchestrator)
- **Platform agent:** `services/vexa-bot/core/src/platforms/msteams` (bot-level Teams code)
- **Service agents:** `services/bot-manager`, `services/transcription-collector`, `services/api-gateway`
- **Sibling:** `features/realtime-transcription/google-meet` (reference implementation)

## How to test

1. Create a live Teams meeting via browser session
2. POST to bot-manager to create a bot targeting the Teams meeting URL
3. Watch bot logs for:
   - `[Captions] ✅ Live captions enabled successfully`
   - `[Teams Captions] Speaker change: (none) → {name}`
   - `[Teams PerSpeaker] Audio routing active (caption-aware with ring buffer)`
   - `[TEAMS SPEAKER] "{name}" — first audio received` for each speaker
   - TranscriptionClient HTTP 200 responses
4. Check Redis: segments with Teams speaker names
5. Check REST: `GET /transcripts/{meeting_id}`

## Diagnostic hints

- **No audio element found:** Teams pre-join screen doesn't have audio until media warm-up completes. Bot must complete join flow first.
- **Speaker detection no signal:** Participant tiles missing `voice-level-stream-outline`. Teams UI may not render these for all participants.
- **Audio routed to wrong speaker:** `speakingStates` map stale, or DOM detection lag. Check `MIN_STATE_CHANGE_MS=200ms` debounce.
- **MS Edge required:** Teams may behave differently in Chromium vs Edge. Bot tries Edge first, falls back to Chromium.

## Critical findings

Save to `tests/findings.md`.
