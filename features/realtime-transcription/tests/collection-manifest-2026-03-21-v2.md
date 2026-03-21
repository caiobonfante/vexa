# Collection Manifest — 2026-03-21 v2

## Context: why this collection run

All certainty checks are at 90+ except VAD (80, indirect). Two controlled datasets exist:
- `collection-run`: 3 TTS speakers, 17 utterances, 100/100
- `panel-20`: 7 real speakers, 20 utterances, 100% captured, 95% speaker

Coverage gaps:
1. **No 5-speaker TTS test** — only real-world panel discussion data has 5+ speakers
2. **No short-phrase stress test** — panel discussion showed a 1.5s split ("she will" -> two segments)
3. **No rapid exchange test** — speaker changes with <1s gaps never tested
4. **VAD never directly tested** — score 80 on indirect evidence only
5. **Previous stress manifest was never collected**

This manifest combines all gaps into one 5-speaker ~3min meeting.

## New dataset

### Dataset ID

`teams-5sp-stress-20260321`

### Hypothesis

```
The pipeline handles 3 TTS speakers at 100% and 7 real speakers at 95%.
A controlled 5-speaker TTS meeting with short phrases, rapid exchanges,
and silence gaps will reveal:
1. Whether 5-speaker caption routing works (speaker identity + audio routing)
2. Whether sub-1s utterances are captured or lost at minAudioDuration=3
3. Whether rapid exchanges cause speaker misattribution
4. Whether 30s silence triggers false flushes or hallucinations

Expected: controls at 100%, short phrases >= 80%, rapid exchanges >= 70%,
silence produces zero segments.
```

### Scenarios

| Tag | Description | Utterances | Expected |
|-----|------------|-----------|----------|
| `control-normal` | >3s gaps, clean transitions | 5 | 100% |
| `short-phrase` | Sub-1s single/two-word utterances | 10 | >= 80% |
| `rapid-exchange` | <1s gaps, back-and-forth | 8 | >= 70% |
| `silence-gap` | 30s silence between speech blocks | 0 segments | Zero hallucination |
| `control-close` | Normal closing utterance after silence | 2 | 100% |

### Script

| # | Speaker | Utterance | T+ | Gap | Tag |
|---|---------|-----------|-----|-----|-----|
| 1 | Alice | "Good morning everyone. Let me walk through the quarterly results for all five regions." | 0s | -- | control-normal |
| 2 | Bob | "Sounds good. Which region should we start with?" | 14s | 3s | control-normal |
| 3 | Charlie | "Let us begin with Europe since that had the strongest growth this quarter." | 21s | 3s | control-normal |
| 4 | Diana | "I agree. The European numbers were really impressive across all segments." | 30s | 3s | control-normal |
| 5 | Eddie | "Before we dive in, I want to flag that the Asia Pacific numbers also exceeded our forecast by a significant margin." | 39s | 3s | control-normal |
| 6 | Alice | "Right." | 52s | 2s | short-phrase |
| 7 | Bob | "OK." | 54s | 2s | short-phrase |
| 8 | Charlie | "Sure." | 56s | 2s | short-phrase |
| 9 | Diana | "Got it." | 58s | 2s | short-phrase |
| 10 | Eddie | "Agreed." | 60s | 2s | short-phrase |
| 11 | Alice | "Yes." | 62s | 2s | short-phrase |
| 12 | Bob | "Makes sense." | 64s | 2s | short-phrase |
| 13 | Charlie | "Noted." | 66s | 2s | short-phrase |
| 14 | Diana | "Done." | 68s | 2s | short-phrase |
| 15 | Eddie | "Perfect." | 70s | 2s | short-phrase |
| -- | (silence) | -- | 72s-102s | 30s | silence-gap |
| 16 | Alice | "Any other thoughts on the budget?" | 104s | 0.8s | rapid-exchange |
| 17 | Bob | "I think we should increase it." | 105.5s | 0.7s | rapid-exchange |
| 18 | Charlie | "Same here." | 107s | 0.7s | rapid-exchange |
| 19 | Diana | "How much more?" | 108s | 0.8s | rapid-exchange |
| 20 | Eddie | "At least twenty percent." | 109s | 0.8s | rapid-exchange |
| 21 | Alice | "That works for me." | 110.5s | 0.7s | rapid-exchange |
| 22 | Bob | "Agreed, let us do it." | 112s | 0.8s | rapid-exchange |
| 23 | Charlie | "I will update the spreadsheet." | 113.5s | 0.8s | rapid-exchange |
| 24 | Diana | "Thanks everyone for a productive discussion. I will send the meeting notes shortly." | 120s | 3s | control-close |
| 25 | Eddie | "Great meeting. Talk to you all next week." | 130s | 3s | control-close |

**Total:** 25 utterances, 5 speakers, ~135s meeting + 30s silence = ~165s
- 5 control-normal
- 10 short-phrase
- 8 rapid-exchange
- 1 silence-gap (30s, expect 0 segments)
- 2 control-close

### TTS Voice Assignment

| Speaker | Voice | Rationale |
|---------|-------|-----------|
| Alice | en_US-lessac-medium | Default female, proven in collection-run |
| Bob | en_US-joe-medium | Male voice, distinct from Alice |
| Charlie | en_US-ryan-medium | Second male, different pitch |
| Diana | en_GB-alba-medium | British female, distinct from Alice |
| Eddie | en_US-arctic-medium | Third male, deeper |

Fallback: if a voice isn't available, use `en_US-lessac-medium` with speed variation.

### Infra requirements

| Param | Value | Notes |
|-------|-------|-------|
| MODEL_SIZE | large-v3-turbo | Match existing |
| COMPUTE_TYPE | int8 | Match existing |
| MIN_AUDIO_DURATION | 3 | Testing if shorts work despite this threshold |
| SUBMIT_INTERVAL | 2 | Current production value |
| CONFIRM_THRESHOLD | 2 | Current production value |
| IDLE_TIMEOUT_SEC | 15 | Must not fire during 30s silence gap (buffer has no audio) |
| PLATFORM | ms-teams | Caption-driven routing |

### Data to capture

| Data | Source | File |
|------|--------|------|
| Per-utterance WAV | TTS service | `audio/teams-5sp-stress/{NN}-{speaker}-{tag}.wav` |
| Ground truth text | Script | `audio/teams-5sp-stress/{NN}-{speaker}-{tag}.txt` |
| Caption events | Bot DOM observer | `audio/teams-5sp-stress/events.txt` |

### Replay readiness

The dataset uses the same format as collection-run and panel-20:
- `{NN}-{speaker}.wav` + `{NN}-{speaker}.txt` pairs
- `events.txt` with caption + speaker change lines
- `DATASET=teams-5sp-stress make play-replay` to test

## Coverage after collection

| Scenario | collection-run | panel-20 | teams-5sp-stress | Total |
|----------|---------------|----------|------------------|-------|
| normal-turns | 10 | 14 | 7 | 31 |
| short-phrase | 3 | 2 | 10 | 15 |
| rapid-exchange | 0 | 3 | 8 | 11 |
| silence-gap | 0 | 0 | 1 | 1 |
| 5+ speakers | 0 | 1 (7sp) | 1 (5sp) | 2 |
