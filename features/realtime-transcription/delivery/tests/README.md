# Delivery Tests

## Why

We found six bugs in the streaming transcription pipeline that were invisible to existing tests:

1. **Duplicate lines** — confirmed and pending text overlapped in the same tick
2. **Content loss** — `advanceOffset` called per segment with absolute offsets that stacked, eating unconfirmed audio
3. **Vanishing text** — last confirmed segments per speaker never published (batch not flushed on cleanup)
4. **Pending blob** — Whisper segments concatenated into one line instead of individual sentences
5. **Context loss** — after buffer trim, Whisper re-interpreted remaining audio differently without context
6. **Always italic** — dashboard's `syntheticSegment` missing `completed` field; empty speaker skipped pending storage

None of these appeared in multi-speaker TTS tests because TTS has clean gaps between utterances. Speaker changes flush the buffer, masking all the mid-stream confirmation bugs. They only appear with continuous single-speaker speech — real conversations, podcasts, interviews.

The testing approach: take real audio (YouTube), feed it through the pipeline, and step through the output tick by tick comparing to ground truth. When something looks wrong, trace it to the code and fix it.

## What

Three tools, each testing a different layer:

| Tool | What it tests | Speed | Needs |
|------|--------------|-------|-------|
| `generate-core.js` | Left side: audio through streaming pipeline | Real-time (audio duration) | Whisper |
| `tick.js` | Rendered output: tick-by-tick file comparison | Instant | Core data only |
| `step.js` | Right side: publish ticks to dashboard via WS | Interactive | Redis, API gateway |

Plus the automated test in the parent directory:

| Tool | What it tests | Speed | Needs |
|------|--------------|-------|-------|
| `../replay-delivery-test.js` | Full delivery: WS + REST + GT coverage | Real-time + 45s wait | Full stack |

## How

### 1. Get audio and ground truth

Download any audio. Generate ground truth with offline Whisper (full file, one shot, best quality).

```bash
# Download
python3.10 -m yt_dlp -x --audio-format wav -o "audio/01-speaker.wav" "$YOUTUBE_URL"

# Resample to 16kHz mono, take first N minutes
ffmpeg -i audio/01-speaker-full.wav -t 120 -ar 16000 -ac 1 audio/01-speaker.wav

# Ground truth
source ../../.env
curl -X POST $TRANSCRIPTION_URL \
  -H "Authorization: Bearer $TRANSCRIPTION_TOKEN" \
  -F "file=@audio/01-speaker.wav" \
  -F "model=large-v3-turbo" \
  -F "timestamp_granularities=segment" \
  -F "response_format=verbose_json" \
  > ground-truth.json
```

Ground truth is the best our Whisper can do on the full file. The streaming pipeline should converge to this. We're not testing Whisper accuracy — we're testing whether the streaming confirmation logic produces clean output that converges without glitches.

### 2. Generate core data

Feed the same audio through the streaming pipeline as a single speaker (Google Meet code path).

```bash
source ../../.env
DATASET=youtube-single-speaker \
  TRANSCRIPTION_URL=$TRANSCRIPTION_URL \
  TRANSCRIPTION_TOKEN=$TRANSCRIPTION_TOKEN \
  node generate-core.js
```

Output: `data/core/{dataset}/transcript.jsonl` — one line per tick, each tick is `{ speaker, confirmed[], pending[] }`.

This runs at real-time speed (120s audio = ~120s to process). Run once, then iterate on rendering with tick.js (instant).

### 3. Step through ticks

Inspect what the dashboard would render at each tick. Three output files updated on each tick.

```bash
# Render tick N
DATASET=youtube-single-speaker node tick.js 5

# Output files:
#   gt.txt           — ground truth segments up to current time
#   rendered.txt     — what the dashboard shows (confirmed + pending)
#   last-rendered.txt — what the dashboard showed on the previous tick
```

Open `rendered.txt` in your editor. Run `node tick.js N` to advance. Compare to `gt.txt` side by side.

- Lines without prefix = confirmed (normal text on dashboard)
- Lines with `[...]` prefix = pending (italic on dashboard)

What to look for:

| Problem | What you see in rendered.txt |
|---------|---------------------------|
| Duplicate lines | Two lines, one starts with the other's text |
| Vanishing text | Line was in last-rendered.txt but gone from rendered.txt |
| Content loss | GT has text that never appears in any tick's rendered.txt |
| Ordering wrong | Pending line appears above confirmed line |
| Always pending | Lines never lose the `[...]` prefix |

When you find something, fix the code, regenerate core data (`node generate-core.js`), re-check the tick.

### 4. Interactive dashboard replay (optional)

Publish ticks one at a time to the real dashboard via WS. You watch the browser and press Enter to advance.

```bash
source ../../.env
DATASET=youtube-single-speaker API_TOKEN=$API_TOKEN REDIS_URL=$REDIS_URL node step.js
```

Opens a meeting, prints the dashboard URL. Each Enter publishes one tick. Useful for verifying the actual dashboard rendering matches what tick.js shows.

### 5. Automated delivery test

Full end-to-end: replay through pipeline, validate WS delivery, check REST persistence.

```bash
source ../../.env
DATASET=teams-3sp-collection API_TOKEN=$API_TOKEN REDIS_URL=$REDIS_URL \
  TRANSCRIPTION_URL=$TRANSCRIPTION_URL TRANSCRIPTION_TOKEN=$TRANSCRIPTION_TOKEN \
  node ../replay-delivery-test.js
```

Validates at every tick: monotonic confirmed count, no phantoms, progressive GT coverage, WS/REST consistency. Reports PASS/FAIL.

## Dataset structure

```
data/raw/{dataset}/
  audio/
    01-speaker.wav          # Source audio (16kHz mono)
  ground-truth.json         # Offline Whisper output (segments with timestamps)

data/core/{dataset}/
  transcript.jsonl          # Pipeline output (one tick per line)
```

Current dataset: `youtube-single-speaker` — first 2 minutes of a podcast interview (Andre Karpathy on No Priors).

## Bugs found with this setup

### 1. advanceOffset over-trim (content loss)

`advanceOffset(buffer, seg.end)` was called inside a loop for each confirmed segment. `seg.end` is absolute within the submitted audio (e.g., 4s, 6s, 8s). But `advanceOffset` adds `seg.end * sampleRate` to `confirmedSamples` — additive. Three calls with 4, 6, 8 advance by 18 seconds instead of 8. The extra audio contained real speech that was never confirmed and never heard again.

**Fix:** Call `advanceOffset` once after the loop with the last segment's end time.

**Found at:** Tick 8 — "The agent part is now taken for granted" was visible as pending, then vanished permanently. Traced to over-trimmed audio buffer.

### 2. Confirmed/pending overlap (duplicate lines)

The pending text comes from the same Whisper call that triggered confirmation. The confirmed portion is a prefix of the pending text. Dashboard shows both — duplicate lines for one tick.

**Fix:** Filter pending segments where `pending.text.startsWith(confirmed.text)` or vice versa.

**Found at:** Live dashboard testing — two lines visible, one a prefix of the other, self-healing after one tick.

### 3. Batch drain on cleanup (vanishing last segments)

Confirmed segments go into `confirmedBatches` and are drained on the speaker's next draft tick. If there's no next tick (speaker's last utterance), the batch is never drained. The segments never reach WS or Postgres.

**Fix:** Flush all remaining batches in `cleanupPerSpeakerPipeline()` before `publishSessionEnd()`.

**Found at:** Automated delivery test — final GT coverage 14/17, missing the last segment per speaker.

### 4. Pending blob (single long italic line)

Whisper returns multiple segments per call, but the pipeline concatenated them into one `result.text` string and published as a single pending entry. Dashboard showed one long italic line instead of individual sentences.

**Fix:** Build one pending entry per Whisper segment, preserving sentence boundaries.

**Found at:** Tick 3-4 comparison — GT had 4 separate lines, rendered had one long blob.

### 5. Context loss after buffer trim

After confirmation, the audio buffer is trimmed. The next Whisper call processes shorter audio without the preceding context. Whisper produces different (worse) text for the same audio because it lost the lead-in context.

**Fix:** Pass last confirmed text as `initial_prompt` parameter to Whisper. The transcription service already supports it (`prompt` form field maps to `initial_prompt` in faster-whisper).

**Found at:** Tick 6 — content that was correctly transcribed at tick 5 changed to different text at tick 6 after buffer trim.

### 6. Dashboard rendering bugs

Two separate issues:
- `syntheticSegment` in `transcript-viewer.tsx` didn't include `completed` field — every segment rendered as italic regardless of confirmation status
- Empty speaker string `""` treated as falsy in `if (speaker)` — pending segments with empty speaker were never stored, never rendered

**Fix:** Add `completed` to syntheticSegment. Check `speaker !== undefined && speaker !== null` instead of truthy check.

**Found at:** Live dashboard testing — all segments italic, pending segments missing entirely.

## Iteration workflow

```
1. Find a bug on live dashboard
2. Get the audio that reproduces it
3. Generate core data:  node generate-core.js
4. Step through ticks:  node tick.js 1, node tick.js 2, ...
5. Find the tick where it breaks
6. Trace to code, fix
7. Recompile:           cd services/vexa-bot/core && npx tsc --outDir dist --skipLibCheck
8. Regenerate core:     node generate-core.js
9. Re-check the tick:   node tick.js N
10. If fixed, rebuild bot image and test live
```

Step 4-9 is the fast inner loop — no meetings, no bots, no WS, instant. Only step 10 requires a live test.
