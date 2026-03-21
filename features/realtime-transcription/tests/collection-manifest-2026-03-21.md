# Collection Manifest — 2026-03-21

## Context: why this collection run

Pipeline replay reached **100%** on the initial collection-run dataset (17 utterances, 3 speakers, ~2 min Teams meeting). Both remaining errors were fixed:
- Mapper single-word boundary split ("Sounds good") — fixed with merge logic
- Stale in-flight Whisper response ("Great meeting everyone") — fixed with generation guard

The dataset is now saturated — 100% means no more signal to extract. But coverage is narrow:
- Only 3 short phrases (sub-1s), all happen to work after the merge fix
- No rapid speaker changes (<1s gaps)
- No 5+ speaker meetings
- No sustained overlaps
- Meeting is only ~2 min — no long-duration buffer behavior tested

This collection expands coverage to stress-test the fixes and find the next set of failures.

## Existing dataset (to formalize)

The current informal collection-run data should be formalized as:

**Dataset ID:** `teams-3sp-normal-20260320`
**Status:** active (control)
**Scenarios:** normal-turns, short-phrase (3 instances), long-monologue
**Scoring:** 100% captured, 100% attribution
**Infra:** large-v3-turbo, int8, minAudioDuration=3, submitInterval=3, confirmThreshold=3

## New dataset

### Dataset ID

`teams-3sp-stress-20260321`

### Hypothesis

```
Hypothesis: The single-word mapper merge fix handles 3 boundary cases but may fail
when 5+ consecutive short phrases cross speaker boundaries in rapid succession,
because the merge heuristic assumes isolated boundary artifacts, not sustained
patterns. Similarly, the stale response guard may not cover all race conditions
when multiple speakers flush simultaneously during rapid exchanges.

Test: 12 short phrases (sub-1s) including 6 consecutive rapid exchanges (<1s gaps),
plus 4 normal-turn controls that must stay at 100%.

Expected outcome: If fixes are robust, short phrases score >= 80% (10/12) and
controls stay at 100%. If the merge heuristic breaks on consecutive shorts,
scoring will drop below 60% on the short-phrase scenario.

Alternative: If scoring is already high (>90%), the mapper merge is sufficient
and the next gap is elsewhere (overlaps, more speakers, GMeet).
```

### Scenarios

| Tag | Description | Utterances | Expected scoring |
|-----|------------|-----------|-----------------|
| `control-normal` | >3s gaps, clean transitions, varied length | 4 | 100% (must match previous) |
| `short-phrase` | Sub-1s single-word/two-word utterances at speaker boundaries | 12 | >= 80% attribution |
| `rapid-exchange` | <1s gaps between speakers, back-and-forth | 8 | >= 70% attribution |
| `control-monologue` | Single speaker, ~15s continuous speech | 1 | 100% content match |

### Script

| # | Speaker | Utterance | Timing (T+) | Gap from prev | Scenario | Notes |
|---|---------|-----------|-------------|---------------|----------|-------|
| 1 | Alice | "Let me start with the quarterly revenue numbers. We exceeded targets in all three regions this quarter." | 0s | -- | control-normal | Warm-up, long sentence |
| 2 | Bob | "That is great news. Which region performed best?" | 15s | 3s | control-normal | Normal turn |
| 3 | Alice | "Europe led with thirty-two percent growth followed by Asia at twenty-one percent." | 22s | 3s | control-normal | Medium sentence |
| 4 | Charlie | "Those numbers are impressive. I think we should increase our European marketing budget for next quarter based on these results." | 32s | 3s | control-monologue | Control monologue ~10s |
| 5 | Alice | "Right." | 48s | 3s | short-phrase | 1 word |
| 6 | Bob | "OK." | 50s | 2s | short-phrase | 1 word, different speaker |
| 7 | Charlie | "Sure." | 52s | 2s | short-phrase | 1 word, third speaker |
| 8 | Alice | "Got it." | 54s | 2s | short-phrase | 2 words |
| 9 | Bob | "Makes sense." | 56s | 2s | short-phrase | 2 words |
| 10 | Charlie | "Agreed." | 58s | 2s | short-phrase | 1 word |
| 11 | Alice | "Yes." | 60s | 2s | short-phrase | Minimal utterance |
| 12 | Bob | "No." | 62s | 2s | short-phrase | Minimal utterance |
| 13 | Charlie | "Done." | 64s | 2s | short-phrase | 1 word |
| 14 | Alice | "Perfect." | 66s | 2s | short-phrase | 1 word |
| 15 | Bob | "Next." | 68s | 2s | short-phrase | 1 word |
| 16 | Charlie | "Go ahead." | 70s | 2s | short-phrase | 2 words |
| 17 | Alice | "What do you think?" | 74s | 0.8s | rapid-exchange | Start rapid block |
| 18 | Bob | "I think we should proceed." | 75s | 0.8s | rapid-exchange | Quick reply |
| 19 | Charlie | "Same here." | 76s | 0.8s | rapid-exchange | Short + rapid |
| 20 | Alice | "Any concerns?" | 77s | 0.8s | rapid-exchange | Question, rapid |
| 21 | Bob | "None from me." | 78s | 0.8s | rapid-exchange | Short reply |
| 22 | Charlie | "All good on my end." | 79s | 0.8s | rapid-exchange | Medium + rapid |
| 23 | Alice | "Then we are aligned." | 80s | 0.8s | rapid-exchange | Closing rapid |
| 24 | Bob | "Moving on to the next topic." | 81s | 0.8s | rapid-exchange | Transition |
| 25 | Charlie | "Thanks everyone for the productive discussion today. Let me send the summary." | 86s | 3s | control-normal | Clean close |

**Total:** 25 utterances, 3 speakers, ~90s meeting
- 4 control-normal + 1 control-monologue = 5 controls
- 12 short-phrase
- 8 rapid-exchange

### Infra requirements

Must match existing dataset for combining:

| Param | Value | Why |
|-------|-------|-----|
| MODEL_SIZE | large-v3-turbo | Match existing dataset |
| COMPUTE_TYPE | int8 | Match existing dataset |
| MIN_AUDIO_DURATION | 3 | Current value, testing if shorts work despite this |
| SUBMIT_INTERVAL | 3 | Current value |
| CONFIRM_THRESHOLD | 3 | Current value |
| IDLE_TIMEOUT_SEC | 15 | Current value |
| PLATFORM | ms-teams | Teams captions are the speaker signal |

### Data to capture

| Data type | Source | Format | File |
|-----------|--------|--------|------|
| Per-utterance audio | TTS service | WAV 16kHz mono | audio/{NN}-{speaker}-{tag}.wav |
| Combined timeline | Replay assembly | WAV 16kHz mono | audio/combined.wav |
| Ground truth | Script + send timestamps | Text: `[GT] {timestamp} {speaker} "{text}"` | ground-truth.txt |
| Caption events | Teams DOM observer | Text log: `{timestamp} TEAMS CAPTION "{speaker}": {text}` | events/caption-events.txt |
| Speaker changes | Teams caption handler | Text log: `{timestamp} Speaker change: {from} -> {to}` | events/speaker-changes.txt |
| Pipeline output | Bot logs | Full bot stderr | pipeline/bot-logs.txt |
| Confirmed segments | onSegmentConfirmed | JSON lines | pipeline/confirmed-segments.jsonl |

### Capture checklist

- [ ] TTS service running, all 3 voices generate audio
- [ ] Teams meeting created and bot joined
- [ ] Caption events appearing in bot logs
- [ ] Speaker changes logged for all 3 speakers
- [ ] onSegmentConfirmed firing (check bot stderr)
- [ ] Ground truth timestamps recorded at send time

### Replay readiness

The existing `production-replay.test.ts` expects:
1. Per-utterance WAV files named `{NN}-{speaker}-{tag}.wav`
2. Events file with caption + speaker change lines
3. Ground truth `.txt` files alongside WAVs

The new dataset uses the same format. The replay test should work without modification. The dataset can be combined with `teams-3sp-normal-20260320` since infra snapshots match.

### Relationship to existing datasets

| Existing | Relationship | Why |
|----------|-------------|-----|
| teams-3sp-normal-20260320 (informal) | Complemented by | New dataset tests edge cases the original doesn't cover. Both can be replayed together. |

## After this manifest

1. Formalize the existing collection-run data into `tests/datasets/teams-3sp-normal-20260320/`
2. If infra is already running and matches requirements → `/collect` directly
3. If infra needs changes → `/env-setup` first

## Coverage map after collection

| Scenario | teams-3sp-normal-20260320 | teams-3sp-stress-20260321 | Total utterances |
|----------|--------------------------|--------------------------|-----------------|
| normal-turns | 10 | 4 | 14 |
| short-phrase | 3 | 12 | 15 |
| rapid-exchange | 0 | 8 | 8 |
| long-monologue | 1 | 1 | 2 |
| overlap | 0 | 0 | 0 |
| 5+ speakers | 0 | 0 | 0 |
