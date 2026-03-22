# Single-Speaker Rendering Test

Feeds real speech through the streaming pipeline and validates the rendered transcript at every tick.

## Why

TTS test audio has clean gaps between utterances. Speaker changes flush the buffer, hiding all mid-stream confirmation bugs. This test uses continuous real speech where confirmations happen mid-buffer — the scenario that triggers duplicate lines, content loss, and rendering glitches.

## Quick start

```bash
# 1. Setup (one-time)
./setup.sh "https://www.youtube.com/watch?v=kwSVtQ7dziU" 120

# 2. Generate core data (re-run after code changes, ~2 min)
./run.sh core

# 3. Step through ticks (instant, repeat as needed)
./run.sh tick 1
./run.sh tick 2
./run.sh tick 3
# compare output/rendered.txt vs output/gt.txt

# 4. Interactive dashboard replay (optional)
./run.sh step
```

## What each command does

| Command | What | Speed | Needs |
|---------|------|-------|-------|
| `./setup.sh URL SECONDS` | Download audio, resample, generate GT | ~30s | Whisper |
| `./run.sh core` | Feed audio through streaming pipeline | Real-time | Whisper |
| `./run.sh tick N` | Render tick N to output files | Instant | Core data only |
| `./run.sh step` | Publish ticks to dashboard one by one | Interactive | Redis, API gateway |

## Output files

After `./run.sh tick N`:

```
output/
  rendered.txt        What the dashboard shows at tick N
  last-rendered.txt   What the dashboard showed at tick N-1
  gt.txt              Ground truth up to current audio time
```

Format:
- Lines without prefix = confirmed (normal text on dashboard)
- `[...]` prefix = pending (italic on dashboard)

## What to look for

| Problem | What you see in rendered.txt |
|---------|---------------------------|
| Duplicate lines | Two lines, one starts with the other's text |
| Vanishing text | Line in last-rendered.txt but gone from rendered.txt |
| Content loss | GT line never appears in any tick |
| Wrong order | `[...]` line above a confirmed line |
| Always pending | Lines never lose `[...]` across many ticks |

## Dataset

```
dataset/
  audio.wav             16kHz mono source audio
  ground-truth.json     Offline Whisper segments
  core/
    transcript.jsonl    Pipeline output (one tick per line)

output/                 Generated per tick (not committed)
  rendered.txt
  last-rendered.txt
  gt.txt
```

## Iteration workflow

```
Find bug on dashboard
  → ./run.sh core        (2 min)
  → ./run.sh tick 1..N   (instant, find the broken tick)
  → fix code
  → recompile            (npx tsc --outDir dist --skipLibCheck)
  → ./run.sh core        (2 min)
  → ./run.sh tick N      (instant, verify fix)
  → rebuild bot image    (make build-bot-image)
  → live test
```
