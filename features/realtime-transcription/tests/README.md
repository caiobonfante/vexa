# Realtime Transcription Tests

## Why this design

This feature follows the [validation cycle](../../README.md#validation-cycle) — see [glossary](../../README.md#glossary) for terms.

A **collection run** (live meeting with TTS bots) is slow, flaky, and expensive. But we need real platform behavior — caption delays, DOM quirks, overlap truncation — because synthetic data won't surface those issues. So we collect reality once and iterate against it many times in the **sandbox**.

The **inner loop** is a **replay** (`make play-replay`): feed **collected data** through the pipeline, **score** against **ground truth**, change code, re-score in seconds. No meetings, no bots, no API costs.

The **outer loop** is triggered by a **plateau**: when remaining errors are in **scenarios** not covered by current collected data, we design a new **script**, run a new **collection run**, and feed the new dataset into the **sandbox**.

```
 COLLECTION RUN                      SANDBOX (inner loop)
 ──────────────                      ────────────────────
 Bots speak from script              Replay collected data offline
 Script = ground truth               Feed through pipeline (real Whisper)
 Collect: audio, caption events,     Score against ground truth
   speaker changes, pipeline output  Change code, replay, re-score
         │                                     │
         │  export collected data              │  plateau?
         └──────────────►──────────────────────┘  need new scenarios?
                                     │
                                     └──► new script → new collection run
                                          → new collected data → sandbox
```

## Current stage: SANDBOX ITERATION

**Scoring**: 81% **caption boundary** accuracy (diverse **scenario**), 88% theoretical with mapper.
**Plateau status**: approaching — short phrase loss and **caption boundary** delay are the remaining errors. Short phrases need a new **scenario** with many sub-1s utterances. **Caption boundary** delay may need audio-energy-based override (new **scenario** needed).

When **scoring** stops improving, transition to **EXPAND** — design **scripts** targeting short-phrase and overlap **scenarios**.

## Testing approach

This **feature** follows the [validation cycle](../../README.md#validation-cycle) with [stage protocol](../../README.md#stages) — see [glossary](../../README.md#glossary) for terms.

### How the cycle applies here

| Cycle step | What we do |
|------------|-----------|
| **Collection run** | Run TTS bots in a live Teams/GMeet meeting. The **script** is the **ground truth**. Capture all **collected data**: audio, caption events, speaker changes, drafts, confirmed segments — all timestamped. |
| **Sandbox iteration** | **Replay** via `make play-replay` — feed collected audio + caption events through the pipeline offline (real Whisper). **Score** word-level speaker attribution against **ground truth**. Change code, replay, re-score in seconds (**inner loop**). |
| **Expand** | When we hit a **plateau**, design new **scenarios** targeting known weaknesses (e.g., added 3-speaker overlap scenario after 2-speaker accuracy plateaued). New **script** → new **collection run** → new **collected data** → back to **sandbox**. |

### Diagnose-fix within the sandbox (inner loop)

1. **Score** — compare pipeline output to **ground truth**, find lost utterances and misattributions
2. **Diagnose** — trace through the pipeline to find the root cause (buffer thresholds, confirmation timing, **caption boundary** delay)
3. **Fix** — modify `SpeakerStreamManager`, speaker-mapper, or related components
4. **Replay** — rerun the same **collected data**, re-score, verify improvement
5. **Repeat** — until you **plateau**, then expand with a new **collection run**

### Test types (from fast to slow)

| Test | Speed | What it validates | Needs Whisper |
|------|-------|------------------|---------------|
| Unit tests (mocked) | Instant | Buffer algorithm, offset logic, flush behavior | No |
| Speaker-mapper tests | Instant | Word→speaker attribution, caption boundaries | No |
| Pipeline WAV tests | Real-time | End-to-end: audio → Whisper → confirmed segments | Yes |
| Real-world replay | Real-time | Pipeline against actual meeting data | Yes |
| Live meeting | Real-time | Full system including bots, captions, speaker detection | Yes + meeting |

### Collected data from collection runs

All **collected data** from Teams **collection runs** with TTS bots (2026-03-20):

| File | What | Events |
|------|------|--------|
| File | What | Events |
|------|------|--------|
| `reference-timestamped-data.json` | **Collected data**: 2-speaker normal-turns **scenario** | 350 events |
| `diverse-test-timestamped-events.txt` | **Collected data**: 3-speaker diverse **scenario** (7 rounds) | 293 events |
| `diverse-test-ground-truth.txt` | **Ground truth**: TTS send times for diverse **script** | 17 utterances |
| `real-meeting-timestamped-events.txt` | **Collected data**: 2-speaker with latest pipeline | 4 confirmed |
| `real-meeting-ground-truth.txt` | **Ground truth**: TTS send times | 4 utterances |

**Caption boundary** patterns: [teams-caption-behavior.md](../ms-teams/teams-caption-behavior.md)
**Replay** architecture: [real-world-replay.md](real-world-replay.md)

## Findings (from collection runs)

### Short phrase loss (5/17 utterances lost in diverse **scenario**)

Single-word utterances consistently lost: "Agreed.", "Thanks.", "OK.", "Perfect.", and short phrase "Plus fifty for events."

**Root cause:** `minAudioDuration=3s` prevents submission of short audio. On speaker change, `flushSpeaker` skips segments < minAudioDuration. The audio stays in the buffer "for next turn" but either gets mixed with stale context or dies at idle timeout.

**Affected:** Any utterance under ~1.5s of speech followed by a speaker change. This **scenario** is common in rapid exchanges.

**Potential fixes:**
- Lower flush threshold (0.5s instead of 3s for speaker-change flush)
- Use caption text directly for sub-1s utterances
- Remove flush skip entirely, let confidence filters catch garbage

**Next step:** Design a **script** with many short utterances to collect more data on this **scenario**.

### Caption boundary delay misattribution (~11% of words at transitions)

Words in the first ~1.5s of a new speaker's turn get attributed to the previous speaker because the **caption boundary** hasn't shifted yet.

**Affected:** 2-3 words per speaker transition in rapid exchanges.

**Scoring:** 88.9% attribution accuracy on **replay**, 100% on live **collection run** (4 segments).

## Test results summary

### Pipeline accuracy (single speaker, WAV tests)

| Test | Analytical | Interpreted | Notes |
|------|-----------|-------------|-------|
| short-sentence (2.8s) | 100% | 100% | Single Whisper call |
| medium-paragraph (13.6s) | 81.4% | ~100% | Diffs are number format only |
| long-monologue (42.9s) | 92.7% | ~100% | Diffs are number/hyphen format |
| noisy-office (SNR=10dB) | 87.1% | ~100% | Robust to office noise |
| noisy-cafe (SNR=10dB) | 87.1% | ~100% | Robust to café noise |

### Speaker attribution scoring (multi-speaker)

| Test | Speakers | Scoring | Lost |
|------|----------|---------|------|
| **Replay** (normal-turns **scenario**) | 2 | 88.9% | **Caption boundary** words |
| **Collection run** (normal turns) | 2 | 100% (4/4 segments) | None |
| **Collection run** (diverse **scenario**, 7 rounds) | 3 | 71% (12/17 utterances) | 5 short phrases |

### Confidence filtering (hallucination combat)

| Filter | Condition | Catches |
|--------|-----------|---------|
| `NO_SPEECH` | `no_speech_prob > 0.5 && avg_logprob < -0.7` | Noise as speech |
| `SHORT_GARBAGE` | `avg_logprob < -0.8 && duration < 2.0` | Silence hallucinations |
| `REPETITIVE` | `compression_ratio > 2.4` | Repeated loops |

Tested: 18/18 silence hallucinations caught ("cards." at logprob=-1.30). Zero false positives on real speech. Zero hallucinations at SNR=10dB.

## Unit tests

**`speaker-streams.test.ts`** — Buffer algorithm (mocked Whisper):
1. Offset advancement — Whisper receives only unconfirmed audio after confirmation
2. Buffer continuity — no full reset, submissions stay small
3. Speaker change flush — emits on `flushSpeaker()`
4. Short segment skip — <2s audio kept for next turn
5. Buffer trim — confirmed audio trimmed at max size

**`speaker-mapper.test.ts`** — Speaker attribution:
1. Two speakers, clean boundaries
2. Three speakers, rapid turns
3. Word straddles boundary — overlap-based attribution
4. Word in gap — nearest speaker
5. Caption events (author:text:timestamp) → boundaries
6. Realistic Teams conversation
7. Caption delay 1.5s — shows boundary shift
8. 5-speaker meeting (201 words, 7 transitions)
9. Single speaker (Google Meet equivalent)

**`replay-meeting.test.ts`** — **Replay** of **collected data**:
- Part A: speaker-mapper with real **caption boundaries** (100% on 69 words)
- Part B: full pipeline **replay** with Whisper + real captions (88.9% **scoring** on 99 words)

## How to run

```bash
cd features/realtime-transcription/tests

# Unit tests (instant, no Whisper)
make unit

# Pipeline tests (real-time, needs Whisper on port 8085)
make play              # medium paragraph
make play-short        # short sentence
make play-long         # 43s monologue
make play-noisy-office # office noise
make play-noisy-cafe   # café noise
make play-noisy-silence # 30s silence gap
make play-speakers     # 3-speaker attribution test

# Full replay of real meeting data
make play-replay

# Everything
make test

# Custom WAV file
make play FILE=/path/to/any.wav

# Against different transcription service
make play TRANSCRIPTION_URL=http://host:port/v1/audio/transcriptions TRANSCRIPTION_TOKEN=xxx
```

## What to look for in logs

### Healthy pipeline
```
  [2.2s] DRAFT  | 214ms | "Let me walk through the full product."
  [4.3s] DRAFT  | 274ms | "Let me walk through the full product roadmap..."

  ✓ [4.3s] CONFIRMED | "Let me walk through the full product roadmap..."
```
- Drafts every ~3s, confirmation when 3 consecutive match
- After confirmation, next draft starts from where previous left off

### Problems to watch for
- **Growing submissions** (2s→4s→6s→...) — not trimming confirmed audio
- **Scattered fragments** (many 4-8s segments) — confirmation too eager
- **Ghost segments** ("cards.", "Thank you.") — silence hallucinations leaking through
- **Lost short phrases** — `[FILTERED]` or flush skip on single-word utterances
- **Wrong speaker** — caption delay shifted boundary words
