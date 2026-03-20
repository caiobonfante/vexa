# Real-World Data Replay

## Why

Live meetings are expensive to run — browser automation, TTS credits, platform flakiness. But synthetic tests use made-up caption timing that may not match reality. Real-world replay bridges this: collect data from a live meeting once (exact caption events, exact timestamps, exact audio), then replay it offline as many times as needed. This is the cheap inner loop of our [dev-test cycle](README.md#why-this-design) — the closest to production accuracy without running a live meeting.

## What We Collected

### Meeting: 2026-03-20, 3 speakers (Alice bot, Bob bot, Dmitry host)

Two conversation sessions in one meeting:

**Session 1 — Normal turns:**
| Speaker | Text (TTS input) | Send time |
|---------|------------------|-----------|
| Alice | "Good morning everyone. I want to start by reviewing our product metrics from last month. We had over fifty thousand active users which is a new record for us." | 14:52:35 |
| Bob | "Those numbers are impressive Alice. Can you break down the user growth by region? I am particularly interested in the European market expansion." | 14:52:49 |
| Alice | "Sure. Europe grew by twenty percent, Asia by fifteen percent, and North America by ten percent." | 14:53:03 |
| Bob | "Makes sense. Localization always helps." | 14:53:13 |

**Session 2 — Overlap + back-to-back:**
| Speaker | Text (TTS input) | Send time | Notes |
|---------|------------------|-----------|-------|
| Alice | "Let me walk through the full product roadmap...redesigned dashboard." | 14:55:12 | ~10s utterance |
| Bob | "I have a question about the API changes. Will they be backwards compatible..." | 14:55:20 | Starts while Alice still speaking (2s overlap) |
| Alice | "Yes fully backwards compatible." | 14:55:32 | Quick reply |
| Bob | "Great thanks." | 14:55:35 | 3s after Alice |

### Data Files

| File | Content | Size |
|------|---------|------|
| `reference-timestamped-data.json` | 350 events with ISO timestamps: 143 caption texts, 10 speaker changes, 77 flushes, 42 drafts, 14 confirmed, 31+33 DOM events | 2568 lines |
| `reference-timestamped-events.txt` | Raw timestamped log lines from `docker logs --timestamps` | Source for JSON |
| `reference-caption-data.json` | Structured events without timestamps (initial extraction) | 273 events |
| `reference-ground-truth-normal.txt` | TTS send timestamps for session 1 | Unix timestamps |
| `reference-ground-truth-overlap.txt` | TTS send timestamps for session 2 | Unix timestamps |
| `reference-bot-logs.txt` | Filtered pipeline events (no timestamps) | 157 lines |
| `reference-raw-logs-full.txt` | Complete bot logs (gitignored, large) | Full output |

### Audio Files (TTS, already in `audio/`)

| File | Speaker | Duration |
|------|---------|----------|
| `short-sentence.wav` | Alice & Charlie | ~3s |
| `medium-paragraph.wav` | Bob | ~14s |
| `long-monologue.wav` | Alice | ~43s |

## Observed Caption Patterns

Documented in detail: [teams-caption-behavior.md](../ms-teams/teams-caption-behavior.md)

Key numbers for replay:

| Parameter | Observed Value |
|-----------|---------------|
| Caption update cadence | ~400ms between word-by-word updates |
| Updates per 10s turn | ~25 |
| Caption delay (first word of new speaker) | ~1.5-2.5s from speech start |
| Caption delay (within turn) | ~300-500ms from word spoken |
| Sentence split frequency | Every 5-8s of speech |
| Speaker change | Atomic, instant, no overlap in captions |
| Overlap handling | First speaker truncated mid-word |

## How to Replay

### Timeline (Session 1, relative to first event at T=0)

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

### Replay Architecture

```
Audio file (reconstructed from TTS WAVs)
  |
  v
SpeakerStreamManager (real-time chunk feeding)
  |
  v
Whisper (word timestamps)
  |                              Caption events (from reference-timestamped-data.json)
  |                                |
  v                                v
speaker-mapper                  captionsToSpeakerBoundaries
  |                                |
  v                                v
mapWordsToSpeakers(whisperWords, captionBoundaries)
  |
  v
Attributed segments → compare to ground truth
```

### Implementation Steps

1. **Reconstruct audio**: Read ground truth send times, concatenate TTS WAVs with correct gap timing
2. **Load caption events**: Parse `reference-timestamped-data.json`, compute relative timestamps from session start
3. **Feed audio at real-time speed**: Same as existing pipeline tests
4. **Replay caption events via timers**: At each event's relative timestamp, fire the caption callback
5. **Collect Whisper word timestamps**: From confirmed segments
6. **Run speaker-mapper**: With caption-derived boundaries
7. **Score**: Per-word attribution accuracy against ground truth time ranges

### Expected Accuracy

Based on observed caption delay (~1.5s mean) and the unit test results:
- **Normal turns (>2s gap)**: ~95%+ attribution accuracy — caption delay doesn't matter because the gap absorbs it
- **Quick back-to-back (<3s gap)**: ~80-85% — first few words of new speaker fall in previous speaker's delayed boundary
- **Overlap**: ~70-75% — truncated speaker loses words, overlapping audio attributed to whoever caption shows

### Run

```bash
make play-replay    # replay real meeting data (when implemented)
```
## Diverse test replay analysis (2026-03-20)

Replayed 16 GT utterances against 14 real caption boundaries.
Caption boundary accuracy: 13/16 = 81%.

3 misattributed by Teams captions (not pipeline):
- 'Thanks.' (Alice at 33.1s) → Charlie boundary (29.5-44.4s)
- 'OK.' (Bob at 37.1s) → Charlie boundary
- 'Plus fifty for events.' (Charlie at 86.2s) → Bob boundary (82.3-90.3s)

Theoretical with carry-forward + mapper: 15/17 = 88%

