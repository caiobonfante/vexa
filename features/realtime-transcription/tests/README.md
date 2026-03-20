# Realtime Transcription Tests

## Why this design

A live meeting (Teams, GMeet, Zoom) involves browser automation, TTS API calls, network latency, and platform-specific caption behavior. It's slow, flaky, and expensive. You can't iterate on speaker attribution by running 50 live meetings a day. But you **need** real platform behavior — caption delays, DOM quirks, overlap truncation — because synthetic data won't surface those issues.

So the design is: **collect reality once, iterate against it many times.**

```
 REAL WORLD                          SANDBOX
 ─────────                           ───────
 Run TTS bots in live meeting        Replay collected data offline
 Scripts = ground truth              Same audio + caption events
 Collect everything:                 Feed through pipeline (real Whisper)
   captions, audio, events, logs     Score against ground truth
                                     Change code, re-score in seconds
         │                                     │
         │  export data                        │  hit accuracy ceiling?
         └──────────────►──────────────────────┘  need new scenarios?
                                     │
                                     │  back to real world
                                     └──────────►─── design new script
                                                     (overlaps, 5 speakers,
                                                      silence gaps, etc.)
                                                     collect new dataset
                                                     feed into sandbox
                                                     repeat
```

The sandbox replay (`make play-replay`) gives a fast, deterministic, free inner loop. You only go back to real world when you've exhausted what the current dataset can teach you — e.g., you fixed all 2-speaker issues and now need 5-speaker overlap data.

## Testing approach

### Iteration cycle

1. **Collect real data** — run TTS speaker bots in a live meeting, collect all raw logs with timestamps (caption events, speaker changes, drafts, confirmed segments). The TTS scripts are the ground truth.
2. **Identify failures** — compare pipeline output to ground truth, find lost utterances and misattributions
3. **Diagnose** — trace through the pipeline to find the root cause (buffer thresholds, confirmation timing, caption delay)
4. **Fix** — modify `SpeakerStreamManager`, speaker-mapper, or related components
5. **Replay** — rerun the same collected data through the updated pipeline, verify improvement
6. **Repeat** — keep iterating in sandbox until you plateau or need new scenarios, then go back to step 1 with a new script

### Test types (from fast to slow)

| Test | Speed | What it validates | Needs Whisper |
|------|-------|------------------|---------------|
| Unit tests (mocked) | Instant | Buffer algorithm, offset logic, flush behavior | No |
| Speaker-mapper tests | Instant | Word→speaker attribution, caption boundaries | No |
| Pipeline WAV tests | Real-time | End-to-end: audio → Whisper → confirmed segments | Yes |
| Real-world replay | Real-time | Pipeline against actual meeting data | Yes |
| Live meeting | Real-time | Full system including bots, captions, speaker detection | Yes + meeting |

### Reference data from live meetings

All data from real Teams meetings with TTS speaker bots (2026-03-20):

| File | What | Events |
|------|------|--------|
| `reference-timestamped-data.json` | 2-speaker normal conversation | 350 events |
| `diverse-test-timestamped-events.txt` | 3-speaker diverse test (7 rounds) | 293 events |
| `diverse-test-ground-truth.txt` | TTS send times for diverse test | 17 utterances |
| `real-meeting-timestamped-events.txt` | 2-speaker with latest pipeline | 4 confirmed |
| `real-meeting-ground-truth.txt` | TTS send times | 4 utterances |

Caption behavior patterns: [teams-caption-behavior.md](../ms-teams/teams-caption-behavior.md)
Replay test plan: [real-world-replay.md](real-world-replay.md)

## Known issues (from real meeting data)

### Short phrase loss (5/17 utterances lost in diverse test)

Single-word utterances consistently lost: "Agreed.", "Thanks.", "OK.", "Perfect.", and short phrase "Plus fifty for events."

**Root cause:** `minAudioDuration=3s` prevents submission of short audio. On speaker change, `flushSpeaker` skips segments < minAudioDuration. The audio stays in the buffer "for next turn" but either gets mixed with stale context or dies at idle timeout.

**Affected:** Any utterance under ~1.5s of speech followed by a speaker change.

**Potential fixes:**
- Lower flush threshold (0.5s instead of 3s for speaker-change flush)
- Use caption text directly for sub-1s utterances
- Remove flush skip entirely, let confidence filters catch garbage

### Caption delay misattribution (~11% of words at transitions)

Words in the first ~1.5s of a new speaker's turn get attributed to the previous speaker because the caption boundary hasn't shifted yet.

**Affected:** 2-3 words per speaker transition in rapid exchanges.

**Tested:** 88.9% attribution accuracy on replay, 100% on real meeting (4 segments).

## Test results summary

### Pipeline accuracy (single speaker, WAV tests)

| Test | Analytical | Interpreted | Notes |
|------|-----------|-------------|-------|
| short-sentence (2.8s) | 100% | 100% | Single Whisper call |
| medium-paragraph (13.6s) | 81.4% | ~100% | Diffs are number format only |
| long-monologue (42.9s) | 92.7% | ~100% | Diffs are number/hyphen format |
| noisy-office (SNR=10dB) | 87.1% | ~100% | Robust to office noise |
| noisy-cafe (SNR=10dB) | 87.1% | ~100% | Robust to café noise |

### Speaker attribution (multi-speaker)

| Test | Speakers | Accuracy | Lost |
|------|----------|----------|------|
| Replay (real caption data) | 2 | 88.9% | Boundary words |
| Live meeting (normal turns) | 2 | 100% (4/4 segments) | None |
| Live meeting (diverse, 7 rounds) | 3 | 71% (12/17 utterances) | 5 short phrases |

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

**`replay-meeting.test.ts`** — Real-world data replay:
- Part A: speaker-mapper with real caption boundaries (100% on 69 words)
- Part B: full pipeline with Whisper + real captions (88.9% on 99 words)

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
