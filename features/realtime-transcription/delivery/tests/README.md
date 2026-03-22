# Delivery Tests

## Why

TTS-generated test audio has clean gaps between utterances. Speaker changes flush the buffer, masking all mid-stream confirmation bugs. Six bugs were found only after feeding continuous real speech (a YouTube podcast) through the pipeline and stepping through the output tick by tick:

1. **advanceOffset over-trim** — called per segment in a loop with absolute offsets that stacked additively, eating unconfirmed audio containing real speech
2. **Confirmed/pending overlap** — same Whisper result produced both confirmed and stale pending text, causing duplicate lines on dashboard
3. **Batch drain on cleanup** — last confirmed segments per speaker never published to WS or persisted to Postgres
4. **Pending blob** — Whisper segments concatenated into one long italic line instead of individual sentences
5. **Context loss after trim** — Whisper re-interpreted remaining audio differently without preceding context
6. **Dashboard rendering** — `syntheticSegment` missing `completed` field (always italic); empty speaker `""` skipped pending storage

## What

Three tools for different layers of validation:

```
generate-core.js   LEFT SIDE    Audio → Whisper → SpeakerStreamManager → transcript.jsonl
tick.js            RENDERING    transcript.jsonl → rendered.txt (what dashboard shows per tick)
step.js            RIGHT SIDE   transcript.jsonl → Redis PUBLISH → WS → dashboard (interactive)
```

Plus the automated delivery test in the parent directory:

```
replay-delivery-test.js   FULL DELIVERY   Pipeline → WS → REST → GT coverage (automated pass/fail)
```

## Prerequisites

```bash
# From this directory
source ../../.env

# Required env vars (all in .env):
#   TRANSCRIPTION_URL    — Whisper endpoint (http://localhost:8083/v1/audio/transcriptions)
#   TRANSCRIPTION_TOKEN  — Whisper auth token
#   API_TOKEN            — API key for WS auth (step.js only)
#   REDIS_URL            — Redis URL (step.js only)

# Required services:
#   Whisper              — for generate-core.js
#   Redis + API gateway  — for step.js
#   Full stack           — for replay-delivery-test.js
```

## Reproducing the test setup from scratch

### Step 1: Get audio

Any audio works. We used the first 2 minutes of a podcast interview.

```bash
# Download from YouTube (requires python3.10 for latest yt-dlp)
python3.10 -m yt_dlp -x --audio-format wav \
  -o "../../data/raw/youtube-single-speaker/audio/01-speaker-full.wav" \
  "https://www.youtube.com/watch?v=kwSVtQ7dziU"

# Resample to 16kHz mono, first 2 minutes
ffmpeg -y \
  -i ../../data/raw/youtube-single-speaker/audio/01-speaker-full.wav \
  -t 120 -ar 16000 -ac 1 \
  ../../data/raw/youtube-single-speaker/audio/01-speaker.wav
```

### Step 2: Generate ground truth

Run Whisper offline on the full audio — one shot, no streaming, best quality. This is the reference transcript.

```bash
source ../../.env

curl -s -X POST "$TRANSCRIPTION_URL" \
  -H "Authorization: Bearer $TRANSCRIPTION_TOKEN" \
  -F "file=@../../data/raw/youtube-single-speaker/audio/01-speaker.wav" \
  -F "model=large-v3-turbo" \
  -F "timestamp_granularities=segment" \
  -F "response_format=verbose_json" \
  > ../../data/raw/youtube-single-speaker/ground-truth.json

# Verify
python3 -c "
import json
d = json.load(open('../../data/raw/youtube-single-speaker/ground-truth.json'))
segs = d.get('segments', d)
print(f'{len(segs)} segments')
for s in segs[:5]:
    print(f'  [{s[\"start\"]:.1f}-{s[\"end\"]:.1f}] {s[\"text\"].strip()[:60]}')
"
```

We're not testing Whisper accuracy — we're testing whether the streaming pipeline produces clean progressive output that converges to this without glitches.

### Step 3: Generate core data

Feed the same audio through the streaming pipeline as a single speaker (Google Meet per-speaker audio path). Runs at real-time speed.

```bash
source ../../.env

DATASET=youtube-single-speaker \
  TRANSCRIPTION_URL=$TRANSCRIPTION_URL \
  TRANSCRIPTION_TOKEN=$TRANSCRIPTION_TOKEN \
  node generate-core.js
```

Output: `../../data/core/youtube-single-speaker/transcript.jsonl`

Each line is one tick: `{ ts, speaker, confirmed: [], pending: [] }`

- `confirmed` — segments that passed the confirmation threshold (text matched on consecutive Whisper calls). Have `completed: true` and `segment_id`.
- `pending` — current unconfirmed Whisper segments. Have `completed: false`. Replaced entirely each tick.

This takes ~2 minutes for 2 minutes of audio. Run once, then iterate with tick.js (instant).

### Step 4: Step through ticks

The fast inner loop. Renders what the dashboard would show at each tick. Three output files updated atomically.

```bash
DATASET=youtube-single-speaker node tick.js 1    # tick 1
DATASET=youtube-single-speaker node tick.js 2    # tick 2
# ...
DATASET=youtube-single-speaker node tick.js 54   # last tick
```

#### Output files

| File | What it shows |
|------|--------------|
| `rendered.txt` | What the dashboard shows at this tick |
| `last-rendered.txt` | What the dashboard showed at the previous tick |
| `gt.txt` | Ground truth segments up to the current audio time |

#### Format

```
Code's not even the right verb anymore, right?        ← confirmed (normal text)
But I have to express my will to my agents for 16...  ← confirmed (normal text)
Manifest.                                             ← confirmed (normal text)
[...] How can I have not just a single session...     ← pending (italic on dashboard)
```

- Lines without prefix = confirmed segments (normal text on dashboard)
- Lines with `[...]` prefix = pending segments (italic on dashboard)

#### What to look for

Open `rendered.txt` and `gt.txt` side by side. After each tick, compare:

| Problem | What you see |
|---------|-------------|
| **Duplicate lines** | Two lines where one starts with the other's text |
| **Vanishing text** | Line was in `last-rendered.txt` but gone from `rendered.txt` |
| **Content loss** | GT has text that never appears in any tick |
| **Wrong order** | `[...]` pending line appears above a confirmed line |
| **Always pending** | Lines never lose the `[...]` prefix across many ticks |
| **Orphan fragment** | Confirmed line starts with a word fragment from previous segment |

When you find a problem:

1. Note the tick number
2. Check the raw tick data: `sed -n 'Np' ../../data/core/youtube-single-speaker/transcript.jsonl | python3 -m json.tool`
3. Trace to the code
4. Fix
5. Recompile: `cd services/vexa-bot/core && npx tsc --outDir dist --skipLibCheck`
6. Regenerate core: `node generate-core.js`
7. Re-check the tick: `node tick.js N`

### Step 5: Interactive dashboard replay (optional)

Publish ticks one at a time to the real dashboard via WS. Watch the browser, press Enter to advance.

```bash
source ../../.env

DATASET=youtube-single-speaker \
  API_TOKEN=$API_TOKEN \
  REDIS_URL=$REDIS_URL \
  node step.js
```

1. Creates a meeting in Postgres
2. Prints dashboard URL — open in browser
3. Each Enter publishes one tick to WS
4. Watch the dashboard update, compare to what tick.js shows

Useful for verifying actual dashboard rendering (CSS, ordering, italic vs normal) matches the text-file view.

### Step 6: Automated delivery test (optional)

Full pipeline replay with automated validation. Tests WS delivery, REST persistence, WS/REST consistency.

```bash
source ../../.env

DATASET=teams-3sp-collection \
  API_TOKEN=$API_TOKEN \
  REDIS_URL=$REDIS_URL \
  TRANSCRIPTION_URL=$TRANSCRIPTION_URL \
  TRANSCRIPTION_TOKEN=$TRANSCRIPTION_TOKEN \
  node ../replay-delivery-test.js
```

Validates at every tick: monotonic confirmed count, speaker correctness, no phantoms, progressive GT coverage. After pipeline completes: REST returns all segments matching WS. Reports PASS/FAIL.

## File reference

### Tools

| File | Purpose | Input | Output |
|------|---------|-------|--------|
| `generate-core.js` | Feed audio through streaming pipeline | WAV file | `transcript.jsonl` |
| `tick.js` | Render one tick to files for comparison | `transcript.jsonl` + tick number | `rendered.txt`, `last-rendered.txt`, `gt.txt` |
| `step.js` | Interactive WS replay to dashboard | `transcript.jsonl` | Publishes to Redis/WS |
| `../replay-delivery-test.js` | Automated delivery validation | `transcript.jsonl` + full stack | PASS/FAIL |

### Dataset structure

```
data/raw/youtube-single-speaker/
  audio/
    01-speaker.wav              # 16kHz mono, first 2 minutes
    01-speaker-full.wav         # Original full download (not committed)
  ground-truth.json             # Offline Whisper output (32 segments)
  events.txt                    # Single speaker start event (for production-replay compat)
  ground-truth.txt              # Simplified GT (for production-replay compat)

data/core/youtube-single-speaker/
  transcript.jsonl              # Pipeline output: 61 ticks, 24 confirmed segments
```

### Generated output (not committed)

```
rendered.txt                    # Current tick's dashboard state
last-rendered.txt               # Previous tick's dashboard state
gt.txt                          # Ground truth up to current time
rendered.md                     # Summary with tick number and new confirmations
```

## How generate-core.js works

```
1. Read WAV file
2. Create SpeakerStreamManager (same config as production bot)
3. Create TranscriptionClient (connects to Whisper service)
4. Add one speaker: "Speaker" / "speaker-0"
5. Feed audio in 256ms chunks at real-time speed
6. On each draft tick (every 2s):
   a. Whisper transcribes the unconfirmed buffer
   b. handleTranscriptionResult checks for confirmation
   c. If confirmed: segments go into confirmedBatches
   d. Drain confirmed batch
   e. Build per-segment pending from Whisper segments
   f. Filter pending that overlaps with confirmed (startsWith check)
   g. Write tick to transcript.jsonl: { confirmed, pending }
   h. Pass last confirmed text as prompt to next Whisper call (context)
7. After audio ends: wait 20s for final processing, flush remaining batches
```

Key differences from the real bot:
- Single speaker (no speaker changes, no flush triggers)
- Audio from file (not from meeting audio capture)
- Uses compiled `dist/` JS (must recompile after source changes)
- No WS publishing (core data only — use step.js for WS)

## How tick.js works

```
1. Load all ticks from transcript.jsonl
2. Load ground truth from ground-truth.json
3. Accumulate dashboard state up to tick N:
   - _confirmed map: segment_id → segment (append only)
   - _pendingBySpeaker map: speaker → segments (replaced each tick)
4. Also accumulate state up to tick N-1 (for last-rendered)
5. Build rendered transcript (same as dashboard's recomputeTranscripts):
   - All confirmed segments
   - Pending segments not overlapping with confirmed (startsWith filter)
   - Sorted by absolute_start_time
6. Write three files:
   - gt.txt: ground truth segments up to max rendered time
   - rendered.txt: current rendered state
   - last-rendered.txt: previous tick's rendered state
```

## How step.js works

```
1. Load ticks from transcript.jsonl
2. Load ground truth from ground-truth.json
3. Create meeting in Postgres (valid 13-digit native ID)
4. Connect to Redis (for PUBLISH)
5. Print dashboard URL
6. For each tick:
   a. Update local state model (confirmed map + pending map)
   b. XADD confirmed segments to transcription_segments stream (persistence)
   c. Store pending in Redis key (TTL 60s)
   d. PUBLISH { type: transcript, speaker, confirmed, pending } to WS channel
   e. Print tick summary and rendered state
   f. Wait for Enter
```

## Iteration workflow

```
Bug found on live dashboard
    ↓
Get the audio that reproduces it
    ↓
node generate-core.js                    ← 2 min (real-time)
    ↓
node tick.js 1 → check rendered.txt      ← instant
node tick.js 2 → check rendered.txt
node tick.js 3 → check rendered.txt
    ↓ found the tick where it breaks
    ↓
Trace to code, fix
    ↓
npx tsc --outDir dist --skipLibCheck     ← recompile
    ↓
node generate-core.js                    ← 2 min
    ↓
node tick.js N → verify fix              ← instant
    ↓ fixed?
    ↓
make build-bot-image                     ← rebuild Docker
    ↓
Live test
```

Steps 3-7 are the fast inner loop — no meetings, no bots, no WS. Only the final step requires a live test.

## Bugs found with this setup

### 1. advanceOffset over-trim

**Tick where found:** 8 — "The agent part is now taken for granted" was visible as pending, then vanished permanently.

**Root cause:** `advanceOffset(buffer, seg.end)` called inside a loop for each confirmed segment. `seg.end` is absolute (4s, 6s, 8s from chunk start). `advanceOffset` adds `seg.end * sampleRate` to `confirmedSamples`. Three calls: 4+6+8 = 18 seconds trimmed instead of 8. Extra 10 seconds of audio eaten.

**Fix:** Call `advanceOffset` once after the loop with the last segment's end time.

### 2. Confirmed/pending overlap

**Tick where found:** Live dashboard — two lines visible, one a prefix of the other.

**Root cause:** Pending built from same Whisper result that triggered confirmation. Pending text starts with confirmed text. Exact-match filter didn't catch it.

**Fix:** Filter pending where `pending.startsWith(confirmed)` or `confirmed.startsWith(pending)`.

### 3. Batch drain on cleanup

**Tick where found:** Automated delivery test — final GT coverage 14/17, missing last segment per speaker.

**Root cause:** Confirmed segments batched per speaker, drained on next draft tick. Last speaker utterance has no next tick. Batch never drained.

**Fix:** Flush all remaining batches in `cleanupPerSpeakerPipeline()` before `publishSessionEnd()`.

### 4. Pending blob

**Tick where found:** 3 — GT had 4 separate lines, rendered had one long blob.

**Root cause:** `result.text` (concatenated) used as single pending entry. Whisper's per-segment boundaries discarded.

**Fix:** Build one pending entry per `result.segments[]`.

### 5. Context loss after trim

**Tick where found:** 6 — content correctly transcribed at tick 5 changed to different text at tick 6 after buffer trim.

**Root cause:** After confirmation, audio buffer trimmed. Next Whisper call processes shorter audio without preceding context. Whisper produces different output.

**Fix:** Pass last confirmed text as `initial_prompt` parameter to Whisper (transcription service already supports `prompt` form field).

### 6. Dashboard rendering

**Where found:** Live dashboard — all segments italic, pending segments missing.

**Root cause:** Two issues:
- `syntheticSegment` in `transcript-viewer.tsx` didn't set `completed` field. `!undefined` = `true` → always italic.
- `if (speaker)` check in `meetings-store.ts` treats empty string `""` as falsy. Pending for unnamed speakers never stored.

**Fix:** Add `completed: group.segments.every(s => s.completed !== false)` to syntheticSegment. Change check to `speaker !== undefined && speaker !== null`.
