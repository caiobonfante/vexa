# /iterate — Sandbox iteration for realtime transcription

You are in **Stage 2: SANDBOX ITERATION** for the realtime-transcription feature.

Read the generic stage protocol first: `/.claude/commands/iterate.md`

## Feature-specific context

### Inventory datasets

Read all manifests in `features/realtime-transcription/tests/datasets/*/manifest.md`.

List active datasets with their scenario tags:

| Dataset | Status | Scenarios | Baseline | Notes |
|---------|--------|-----------|----------|-------|
| {id} | active | {tags} | {X}% | {what it tests} |

### How to replay

```bash
cd features/realtime-transcription/tests

# Replay a specific dataset
make play-replay DATASET={id}

# Replay all active datasets
make play-replay-all

# Individual pipeline tests (single speaker, not dataset-based)
make play-short        # 3s sentence
make play-medium       # 14s paragraph
make play-long         # 43s monologue
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

### Pipeline params to tune

These are in `.env` and/or hardcoded in `speaker-streams.ts`:

| Param | Current | Effect of lowering | Effect of raising |
|-------|---------|-------------------|-------------------|
| `minAudioDuration` | 3s | Catches shorter phrases, but more garbage submissions | Loses short phrases |
| `submitInterval` | 3s | Lower latency, more Whisper calls | Higher latency, fewer calls |
| `confirmThreshold` | 3 | Faster confirmation, risk of premature confirm | Slower confirmation, more stable |
| `idleTimeoutSec` | 15s | Faster flush on silence, but false flushes | Delayed flush, stale buffer |
| `maxSpeechDurationSec` | 15s | Shorter Whisper segments | Longer context per submission |

### Iteration tracking

When reporting each iteration, include which dataset(s) you replayed:

```
Iteration {N}:
  teams-3sp-diverse-20260320: {X}% → {Y}% ({+/-Z}%) [target]
  teams-2sp-normal-20260320:  {X}% → {Y}% ({+/-Z}%) [control]
  Fix: {description}
  Remaining: {count} errors in scenarios: {tags}
  Status: {iterating | plateau | target met}
```

### When you've hit a plateau

If scoring is stuck and remaining errors are in scenarios not covered by any active dataset:
- **Short phrases** not in any dataset → need `short-phrase` scenario → `/expand`
- **Overlap** not in any dataset → need `overlap` scenario → `/expand`
- **More speakers** needed → need `5sp` dataset → `/expand`
- **Different platform (GMeet)** → need GMeet dataset → `/expand`
- **Longer meetings** → need `long-meeting` dataset (>5min) → `/expand`

Report the plateau with: scoring per dataset, per scenario, which scenarios are missing, and what new datasets would help.

**Then immediately proceed to `/expand`** — do not wait for human input. The expand stage will design new scenarios, after which you create a fresh meeting (`/host-teams-meeting-auto`) and collect again (`/collect`). Keep looping until quality is production-grade.
