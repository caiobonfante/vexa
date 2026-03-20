# /iterate — Sandbox iteration for realtime transcription

You are in **Stage 2: SANDBOX ITERATION** for the realtime-transcription feature.

Read the generic stage protocol first: `/.claude/commands/iterate.md`

## Feature-specific context

### How to replay and score

```bash
cd features/realtime-transcription/tests

# Full replay of collected data (real Whisper, real caption events)
make play-replay

# Individual pipeline tests (single speaker, specific scenarios)
make play-short        # 3s sentence
make play-medium       # 14s paragraph
make play-long         # 43s monologue
make play-noisy-office # office noise
make play-speakers     # 3-speaker attribution

# Unit tests (mocked Whisper, instant)
make unit

# Everything
make test
```

### Key source files to modify

| Component | File | What it does |
|-----------|------|-------------|
| Buffer/submission | `services/vexa-bot/core/src/services/speaker-streams.ts` | Audio buffering, Whisper submission, confirmation logic |
| Speaker attribution | `services/vexa-bot/core/src/services/speaker-mapper.ts` | Maps Whisper word timestamps to caption boundaries |
| Confidence filters | `services/vexa-bot/core/src/services/speaker-streams.ts` | no_speech, short_garbage, repetitive filters |
| Transcription client | `services/vexa-bot/core/src/services/transcription-client.ts` | HTTP POST to Whisper, retry logic |

### Common root causes and where to look

| Symptom | Root cause area | File:function |
|---------|----------------|---------------|
| Short phrases lost | `minAudioDuration` threshold in flush logic | `speaker-streams.ts:flushSpeaker` |
| Wrong speaker on boundary words | Caption boundary delay (~1.5s) | `speaker-mapper.ts:mapWordsToSpeakers` |
| Hallucinated text from silence | Confidence filter thresholds | `speaker-streams.ts:handleTranscriptionResult` |
| Growing submission size | Offset not advancing after confirmation | `speaker-streams.ts:advanceOffset` |
| Segments never confirm | `confirmThreshold` too strict or text keeps changing | `speaker-streams.ts:checkConfirmation` |

### Current scoring baseline

Read `tests/findings.md` and `tests/README.md` (section "Current stage") for the latest numbers. As of last update:
- Normal turns: ~100% (4/4 segments)
- Diverse scenario: 71% (12/17 utterances) — short phrases lost
- Replay attribution: 81% caption boundary accuracy, 88% theoretical with mapper
- Pipeline accuracy: 87-100% content accuracy depending on noise

### Pipeline params to tune

These are in `.env` and/or hardcoded in `speaker-streams.ts`:

| Param | Current | Effect of lowering | Effect of raising |
|-------|---------|-------------------|-------------------|
| `minAudioDuration` | 3s | Catches shorter phrases, but more garbage submissions | Loses short phrases |
| `submitInterval` | 3s | Lower latency, more Whisper calls | Higher latency, fewer calls |
| `confirmThreshold` | 3 | Faster confirmation, risk of premature confirm | Slower confirmation, more stable |
| `idleTimeoutSec` | 15s | Faster flush on silence, but false flushes | Delayed flush, stale buffer |
| `maxSpeechDurationSec` | 15s | Shorter Whisper segments | Longer context per submission |

### When you've hit a plateau

If scoring is stuck and remaining errors are in:
- **Short phrases not in collected data** → need short-phrase scenario → `/expand`
- **Overlap behavior not in collected data** → need overlap scenario → `/expand`
- **Different platform (GMeet)** → need GMeet collection run → `/expand`

Report the plateau clearly: what scoring, what errors, what scenarios are missing.
