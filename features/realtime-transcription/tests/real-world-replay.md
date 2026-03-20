# Replay Architecture

**Replay** is the core of the **inner loop** — see [glossary](../../README.md#glossary) for terms.

## Why

A **collection run** is expensive: browser automation, TTS credits, platform flakiness. But synthetic tests use made-up caption timing that may not match reality. **Replay** bridges this: run one **collection run** to capture **collected data** (exact caption events, exact timestamps, exact audio), then **replay** it in the **sandbox** as many times as needed. This is the cheap **inner loop** — the closest to production **scoring** without running a live meeting.

## Collected data

### Collection run: 2026-03-20, 3 speakers (Alice bot, Bob bot, Dmitry host)

Two **scenarios** in one **collection run**:

**Scenario 1 — Normal turns (>2s gaps):**
| Speaker | Text (TTS input) | Send time |
|---------|------------------|-----------|
| Alice | "Good morning everyone. I want to start by reviewing our product metrics from last month. We had over fifty thousand active users which is a new record for us." | 14:52:35 |
| Bob | "Those numbers are impressive Alice. Can you break down the user growth by region? I am particularly interested in the European market expansion." | 14:52:49 |
| Alice | "Sure. Europe grew by twenty percent, Asia by fifteen percent, and North America by ten percent." | 14:53:03 |
| Bob | "Makes sense. Localization always helps." | 14:53:13 |

**Scenario 2 — Overlap + back-to-back (<3s gaps):**
| Speaker | Text (TTS input) | Send time | Notes |
|---------|------------------|-----------|-------|
| Alice | "Let me walk through the full product roadmap...redesigned dashboard." | 14:55:12 | ~10s utterance |
| Bob | "I have a question about the API changes. Will they be backwards compatible..." | 14:55:20 | Starts while Alice still speaking (2s overlap) |
| Alice | "Yes fully backwards compatible." | 14:55:32 | Quick reply |
| Bob | "Great thanks." | 14:55:35 | 3s after Alice |

### Data files

| File | Type | Size |
|------|------|------|
| `reference-timestamped-data.json` | **Collected data**: 350 events (143 caption texts, 10 speaker changes, 77 flushes, 42 drafts, 14 confirmed, 31+33 DOM events) | 2568 lines |
| `reference-timestamped-events.txt` | **Collected data**: raw timestamped log lines from `docker logs --timestamps` | Source for JSON |
| `reference-caption-data.json` | **Collected data**: structured **caption boundary** events without timestamps | 273 events |
| `reference-ground-truth-normal.txt` | **Ground truth**: TTS send timestamps for scenario 1 **script** | Unix timestamps |
| `reference-ground-truth-overlap.txt` | **Ground truth**: TTS send timestamps for scenario 2 **script** | Unix timestamps |
| `reference-bot-logs.txt` | **Collected data**: filtered pipeline events (no timestamps) | 157 lines |
| `reference-raw-logs-full.txt` | **Collected data**: complete bot logs (gitignored, large) | Full output |

### Audio Files (TTS, already in `audio/`)

| File | Speaker | Duration |
|------|---------|----------|
| `short-sentence.wav` | Alice & Charlie | ~3s |
| `medium-paragraph.wav` | Bob | ~14s |
| `long-monologue.wav` | Alice | ~43s |

## Observed caption boundary behavior

Documented in detail: [teams-caption-behavior.md](../ms-teams/teams-caption-behavior.md)

Key numbers for **replay** (from **collected data**):

| Parameter | Observed Value |
|-----------|---------------|
| Caption update cadence | ~400ms between word-by-word updates |
| Updates per 10s turn | ~25 |
| **Caption boundary** delay (first word of new speaker) | ~1.5-2.5s from speech start |
| **Caption boundary** delay (within turn) | ~300-500ms from word spoken |
| Sentence split frequency | Every 5-8s of speech |
| Speaker change | Atomic, instant, no overlap in captions |
| Overlap handling | First speaker truncated mid-word |

## How to replay

### Timeline (scenario 1, relative to first event at T=0)

```
 0.0s                          26.6s         40.2s         54.8s         64.5s
  |                              |             |             |             |
  Bot joins                   Alice          Bob           Alice          Bob
  meeting                     starts         starts        starts         starts
                               |              |             |              |
                           "Good morning"  "Those"       "Sure"        "Makes sense"
                               |              |             |              |
                          First caption    Speaker       Speaker        Speaker
                          event fires      change        change         change
```

### Replay architecture

```
Audio (from collected data — reconstructed from TTS WAVs)
  |
  v
SpeakerStreamManager (real-time chunk feeding)
  |
  v
Whisper (word timestamps)
  |                              Caption events (collected data → caption boundaries)
  |                                |
  v                                v
speaker-mapper                  captionsToSpeakerBoundaries
  |                                |
  v                                v
mapWordsToSpeakers(whisperWords, captionBoundaries)
  |
  v
Attributed segments → scoring against ground truth
```

### Replay steps

1. **Reconstruct audio**: Read **ground truth** send times, concatenate TTS WAVs with correct gap timing
2. **Load collected data**: Parse `reference-timestamped-data.json`, compute relative timestamps from session start
3. **Feed audio at real-time speed**: Same as existing pipeline tests
4. **Replay caption events via timers**: At each event's relative timestamp, fire the caption callback → **caption boundaries**
5. **Collect Whisper word timestamps**: From confirmed segments
6. **Run speaker-mapper**: Map words to speakers using **caption boundaries**
7. **Score**: Per-word attribution accuracy against **ground truth** time ranges

### Expected scoring by scenario

Based on observed **caption boundary** delay (~1.5s mean):
- **Normal turns scenario (>2s gap)**: ~95%+ — **caption boundary** delay doesn't matter because the gap absorbs it
- **Rapid exchange scenario (<3s gap)**: ~80-85% — first few words of new speaker fall in previous speaker's delayed **caption boundary**
- **Overlap scenario**: ~70-75% — truncated speaker loses words, overlapping audio attributed to whoever caption shows

### Run

```bash
make play-replay    # replay collected data in sandbox
```

## Scoring results: diverse scenario replay (2026-03-20)

**Replay** of 16 **ground truth** utterances against 14 real **caption boundaries**.
**Scoring**: 13/16 = 81% caption boundary accuracy.

3 misattributed by Teams **caption boundaries** (not pipeline):
- 'Thanks.' (Alice at 33.1s) → Charlie **caption boundary** (29.5-44.4s)
- 'OK.' (Bob at 37.1s) → Charlie **caption boundary**
- 'Plus fifty for events.' (Charlie at 86.2s) → Bob **caption boundary** (82.3-90.3s)

Theoretical with carry-forward + mapper: 15/17 = 88%

**Plateau**: remaining 2 errors are platform-level **caption boundary** misattribution — can't be fixed in pipeline. Need new **scenarios** to test workarounds (e.g., using audio energy to override **caption boundaries**).

