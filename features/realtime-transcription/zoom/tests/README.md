# Zoom Transcription Tests

## Why this design

Same approach as parent ([tests/README.md](../../tests/README.md)): collect reality once (live Zoom meeting with TTS bots), iterate against it many times in the sandbox (replay). The inner loop is replay + score, the outer loop is triggered by a plateau.

## Current stage: BLOCKED BY MVP0

Cannot run any tests until MVP0 (audio channel join) is complete. Bot joins meeting but audio is silent.

## Testing approach

This feature follows the same [validation cycle](../../README.md#validation-cycle) as GMeet/Teams.

### How the cycle applies here

| Cycle step | What we do |
|------------|-----------|
| **Collection run** | Run TTS bots in a live Zoom meeting. The script is the ground truth. Capture: audio, speaker events, confirmed segments. |
| **Sandbox iteration** | Replay collected audio through the pipeline offline (real Whisper). Score against ground truth. Inner loop. |
| **Expand** | When we hit a plateau, design new scenarios. New script -> new collection run -> new data -> back to sandbox. |

### Test types (from fast to slow)

| Test | Speed | What it validates | Needs Whisper | Status |
|------|-------|------------------|---------------|--------|
| Unit tests (mocked) | Instant | Buffer algorithm, voting logic | No | Not started |
| Mock HTML page | Instant | Speaker identity selectors, audio element discovery | No | Designed (shift-left-testing-design.md) |
| Pipeline WAV tests | Real-time | Audio -> Whisper -> confirmed segments | Yes | Shared with parent (make play) |
| E2E live meeting | Real-time | Full system with Zoom platform | Yes + meeting | Script ready, blocked by MVP0 |

### Test scripts

| Script | Location | What it tests | Prerequisite |
|--------|----------|---------------|-------------|
| `e2e/test-e2e.sh` | This dir | Full pipeline: TTS bots -> Zoom -> transcription -> Postgres | MVP0 + MVP1 + MVP3 |

### Shared infrastructure

| Resource | Location | Shared with |
|----------|----------|-------------|
| Scorer | `google-meet/tests/e2e/score-e2e.py` | All platforms (platform-agnostic) |
| Ground truth script | Same 9 utterances as GMeet/Teams | Cross-platform comparison |
| WAV replay | `tests/Makefile` (`make play-*`) | All platforms |
| Unit tests | `tests/Makefile` (`make unit`) | All platforms |
| TTS audio generation | `tests/generate-test-audio.sh` | All platforms |

### Datasets

No datasets yet. Will be populated after MVP3 (TTS bot testing infrastructure).

| Dataset | Stage | Contents | Status |
|---------|-------|----------|--------|
| `data/raw/zoom-3sp-basic/` | raw | 3 speakers, 9 utterances. Audio + speaker events + ground truth. | Not collected |
| `data/raw/zoom-3sp-stress/` | raw | 3 speakers, 20 utterances, stress scenarios. | Not collected |
| `data/core/zoom-3sp-basic/` | core | Pipeline output. | Not generated |

## Zoom-specific diagnostics

### What to look for in logs

```
# Audio channel joined (MVP0)
[Zoom Web] Joined with Computer Audio

# Per-speaker elements found (MVP0)
[PerSpeaker] Found 3 media elements with audio

# Speaker identity (MVP1)
[SpeakerIdentity] Track 0 -> "Alice" LOCKED PERMANENTLY

# Active speaker detection (MVP1)
SPEAKER_START: Alice
SPEAKER_END: Alice

# Transcription (MVP2)
[CONFIRMED] Alice | en | ... | "Welcome everyone..."
```

### Problems to watch for

- **No "Joined with Computer Audio"** — MVP0 incomplete, bot didn't join audio channel
- **Media elements found but amplitude = 0** — Audio channel not joined, or Zoom web client not rendering audio elements
- **SPEAKER_START only shows host** — TTS bots not detected as speakers (ejected? audio not reaching meeting?)
- **All tracks vote for same name** — `isMostRecentlyActiveTrack()` not gating correctly
- **Segments with empty speaker** — `resolveZoomSpeakerName()` returning null (both paths failed)
