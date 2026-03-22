# Single-Speaker Pipeline Test

Debug and evaluate the real-time transcription pipeline in its simplest form — one audio file, one speaker, no meeting complexity. See what happens at every stage from audio input to rendered output, tick by tick.

## Why

The pipeline has three stages and we need to see the output at each:

```
AUDIO → [LEFT SIDE] → CORE DATA → [RIGHT SIDE] → RENDERED OUTPUT
```

- **Left side** (expensive): audio → Whisper → SpeakerStreamManager → confirmation logic → core ticks. Runs at real-time speed. Re-run only when pipeline code changes.
- **Right side** (cheap): core ticks → dashboard state model → rendered text. Instant. Re-run as many times as needed.

We take any audio (YouTube video, podcast, recording), create ground truth with a single offline Whisper pass, and feed the same audio as a single-speaker meeting through the streaming pipeline. Then we walk through the output tick by tick, comparing what the user would see on the dashboard against what the audio actually says.

When something looks wrong, we decide: is it worth fixing? If yes, we identify whether the issue is on the left side (pipeline code) or the right side (rendering/delivery), fix it, and re-run only the affected side.

## Data stages

### Ground truth

One offline Whisper pass on the full audio file — no streaming, no chunking, best quality. This is the reference: what the text should say.

```
ground-truth.json: [
  { "text": "Code's not even the right verb anymore, right?", "start": 0.0, "end": 2.1 },
  { "text": "But I have to express my will to my agents...", "start": 2.1, "end": 6.8 },
  ...
]
```

### Core data

The streaming pipeline's output. One tick per line, each tick is what the bot would publish to WS at that moment — confirmed segments (locked in) and pending segments (current draft, may change next tick).

```
transcript.jsonl (line = tick):
  { "confirmed": [{ "text": "...", "completed": true, "segment_id": "..." }],
    "pending":   [{ "text": "...", "completed": false }] }
```

Confirmed segments accumulate — once confirmed, they never change. Pending segments are replaced entirely each tick. What the dashboard shows at any moment is all confirmed + current pending.

### Rendered output

What the user sees on the dashboard at a given tick. Built from core data using the same state model as the dashboard:

```
rendered.txt:
  Code's not even the right verb anymore, right?       ← confirmed (normal text)
  But I have to express my will to my agents...        ← confirmed (normal text)
  [...] How can I have not just a single session...    ← pending (italic)
```

## Iteration loop

```
./run.sh core                    ← LEFT SIDE: generate core data (~2 min)
    ↓
./run.sh tick 1                  ← RIGHT SIDE: render tick 1 (instant)
./run.sh tick 2                  ← render tick 2
./run.sh tick 3                  ← render tick 3
    ↓                               compare rendered.txt vs gt.txt
    ↓                               compare rendered.txt vs last-rendered.txt
    ↓
Found issue at tick N
    ↓
Is it worth fixing?
    ↓ yes
Where is the issue?
    ├─ RIGHT SIDE (rendering/delivery)
    │   Fix dashboard code
    │   ./run.sh tick N              ← instant re-check
    │
    └─ LEFT SIDE (pipeline/Whisper)
        Fix pipeline code
        Recompile: npx tsc --outDir dist --skipLibCheck
        ./run.sh core                ← re-generate (~2 min)
        ./run.sh tick N              ← verify fix
    ↓
Fixed? → next tick
    ↓
All ticks clean? → rebuild bot image → live test
```

The key insight: right-side iteration is free (instant). Left-side iteration costs ~2 minutes per cycle. So first check if an issue is rendering-only (right side) before re-running the pipeline (left side).

## Quick start

```bash
# 1. Setup (one-time): download audio, resample, generate ground truth
./setup.sh "https://www.youtube.com/watch?v=kwSVtQ7dziU" 120

# 2. Generate core data (re-run after pipeline code changes)
./run.sh core

# 3. Step through ticks (instant, repeat as needed)
./run.sh tick 1        # look at output/rendered.txt vs output/gt.txt
./run.sh tick 2
./run.sh tick 3
# ...

# 4. Validate core data for known issues (instant)
./run.sh validate

# 5. Interactive dashboard replay (optional, needs Redis + API gateway)
./run.sh step
```

## Commands

| Command | What | Cost |
|---------|------|------|
| `./setup.sh URL SECONDS` | Download audio, resample to 16kHz mono, generate GT | ~30s |
| `./run.sh core` | Feed audio through streaming pipeline → `transcript.jsonl` | ~2 min |
| `./run.sh tick N` | Render tick N → `output/rendered.txt`, `output/gt.txt`, `output/last-rendered.txt` | Instant |
| `./run.sh tick all` | Render all ticks, one-line summary each | Instant |
| `./run.sh validate` | Check core data for overlaps, missing fields, regressions | Instant |
| `./run.sh step` | Publish ticks to dashboard via WS, one at a time | Interactive |

## What to look for at each tick

Compare `output/rendered.txt` (what the user sees) against `output/gt.txt` (what was actually said) and `output/last-rendered.txt` (what the user saw one tick ago):

| Problem | How to spot it | Which side |
|---------|---------------|-----------|
| Duplicate lines | rendered.txt has two lines, one starts with the other | Left (pending overlap) |
| Vanishing text | Line in last-rendered.txt gone from rendered.txt | Left (buffer trim) |
| Content loss | GT text never appears in any tick | Left (advanceOffset) |
| Wrong order | `[...]` pending above confirmed line | Left (windowStartMs) |
| Always pending | Lines never lose `[...]` across ticks | Right (completed field) |
| Missing lines | Fewer lines in rendered.txt than expected | Right (empty speaker) |

## Files

```
single-speaker/
  README.md             This file
  setup.sh              Download + resample + ground truth
  run.sh                All test commands
  .gitignore            Excludes audio, core data, output
  dataset/              Created by setup.sh
    audio.wav           16kHz mono source audio
    ground-truth.json   Offline Whisper segments
    metadata.txt        Source URL, duration, date
    core/               Created by run.sh core
      transcript.jsonl  Pipeline output (one tick per line)
  output/               Created by run.sh tick (not committed)
    rendered.txt        Dashboard state at current tick
    last-rendered.txt   Dashboard state at previous tick
    gt.txt              Ground truth up to current time
```
