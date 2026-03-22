# YouTube Multi-Speaker Pipeline Test

Debug and evaluate the real-time transcription pipeline with multi-speaker real speech from YouTube videos. Same principles as `single-speaker/` but with speaker attribution in the loop.

## Why

`single-speaker/` tests the streaming confirmation logic — does continuous speech produce clean rendered output tick by tick? This test adds the next layer: when multiple speakers are separated into per-speaker audio and played from separate bots, does the pipeline correctly attribute and render each speaker's segments?

Single-speaker catches pipeline bugs (content loss, duplicate lines, rendering). Multi-speaker catches attribution bugs (wrong speaker, missing speaker, speaker merge).

## Data stages

```
AUDIO → [GROUND TRUTH] → [LEFT SIDE] → CORE DATA → [RIGHT SIDE] → RENDERED OUTPUT
```

### Ground truth

Two steps:
1. Offline Whisper on full audio → timestamped segments
2. AI speaker assignment (Claude) → each segment gets a speaker label

```
ground-truth.json: [
  { "speaker": "Speaker-A", "text": "Welcome to the show...", "start": 0.0, "end": 4.2 },
  { "speaker": "Speaker-B", "text": "Thanks for having me...", "start": 4.5, "end": 9.1 },
  ...
]
```

Speaker names are arbitrary labels. What matters is consistency — the same voice gets the same label throughout.

### Per-speaker audio

Cut the source audio into per-speaker files using GT timestamps. Each speaker's segments become a playlist that a bot plays into the meeting at the correct offsets.

```
dataset/
  speakers/
    speaker-a/
      segments.json       # [{ file, start, end }]
      00-segment.wav
      01-segment.wav
    speaker-b/
      segments.json
      00-segment.wav
```

### Core data

Same as single-speaker: `transcript.jsonl` with `{ confirmed[], pending[] }` per tick. But now each segment has a `speaker` field and the validation checks attribution against GT.

### Rendered output

Same tick-by-tick comparison, but now checking both text content AND speaker assignment per line.

## Iteration loop

Same cost model as single-speaker:
- **Right side** (cheap): core ticks → rendered output. Instant.
- **Left side** (expensive): audio → Whisper → pipeline. Real-time speed.
- **Collection** (most expensive): bots playing into a live meeting. Only when left-side pipeline changes require new raw data.

```
./setup.sh VIDEO_URL SECONDS N_SPEAKERS     ← download, GT, split audio
    ↓
[bots play into meeting, capture output]    ← expensive, do once
    ↓
./run.sh core                               ← or replay from captured data
    ↓
./run.sh tick 1                             ← instant
./run.sh tick 2
    ↓
Found issue at tick N
    ↓
├─ RIGHT SIDE → fix rendering → ./run.sh tick N
├─ LEFT SIDE → fix pipeline → recompile → ./run.sh core → ./run.sh tick N
└─ COLLECTION → fix capture → re-run bots → ./run.sh core → ./run.sh tick N
```

## Prerequisites

Before building this pipeline, two things need validation:

### 1. AI speaker assignment accuracy

Can Claude reliably assign speaker labels to Whisper segments using only text and timestamps?

**How to validate:**
1. Download a 2-3 speaker interview from YouTube
2. Run offline Whisper → segments
3. Feed segments to Claude: "assign Speaker-A/B/C to each segment based on conversational context"
4. Watch first 2-3 minutes of video, check assignments against who's actually speaking

**Pass:** 80%+ correct. Boundary errors (speaker changes mid-segment) are acceptable.

### 2. Streaming vs offline Whisper comparison

When the same audio goes through offline Whisper vs streaming Whisper (chunked, real-time), how different are the results?

**How to validate:**
1. Use `single-speaker/` test setup — already generates both offline GT and streaming core data
2. Compare final confirmed text against GT
3. Check keyword overlap: 50%+ per segment = match

**Pass:** 80%+ of segments have a fuzzy match. This is already validated by the single-speaker test — our results showed 17/17 GT coverage.

## What to build

| Component | Status | Work needed |
|-----------|--------|-------------|
| YouTube download + Whisper | Done | `setup.sh` from single-speaker |
| AI speaker assignment | Needs validation | Claude prompt + manual check |
| Audio splitter | Not built | `ffmpeg -ss {start} -to {end}` per segment |
| Bot playlist player | Not built | Extend `TTSPlaybackService.playFile()` with offsets |
| Left-side scorer | Partial | Adapt production-replay scoring for GT format |
| Right-side replay | Done | `tick.js` / `step.js` work with any core data |

## Dataset structure

```
youtube-pipeline/
  README.md
  setup.sh                      # Download, GT, speaker assignment, split
  run.sh                        # core, tick, step, validate
  .gitignore
  dataset/
    source-16k.wav              # Full audio (16kHz mono)
    whisper-segments.json       # Offline Whisper output
    ground-truth.json           # Speaker-assigned segments
    speakers/
      speaker-a/
        segments.json
        *.wav
      speaker-b/
        segments.json
        *.wav
    core/
      transcript.jsonl          # Pipeline output
  output/
    rendered.txt
    last-rendered.txt
    gt.txt
```
