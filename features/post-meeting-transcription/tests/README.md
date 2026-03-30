# Post-Meeting Transcription — Test Strategy

## Inputs

Every evaluation requires two things:

1. **Ground truth file** (`ground-truth.txt`) — what was said, by whom, when:
   ```
   [GT] 1774222620.172614 Alice "Good morning everyone."
   [GT] 1774222628.214414 Bob "Thanks Alice."
   ```
   Produced during collection: the agent writes each line at the moment it sends the `/speak` command, using `$(date +%s.%N)` for the wall-clock timestamp.

2. **Transcript output** — what the pipeline produced. Source depends on which gate:
   - Gate 1-2: query Postgres directly (deferred transcription writes there)
   - Gate 3-4: query via GET /transcripts REST endpoint (what the user sees)

   Postgres query:
   ```sql
   SELECT start_time, end_time, speaker, text
   FROM transcriptions WHERE meeting_id = {ID} ORDER BY start_time;
   ```
   Each row has: `start_time` (float, seconds relative to recording start), `end_time`, `speaker` (string, e.g. "Alice (Guest)"), `text`.

## How each metric is validated

### 1. Segment Capture Rate

**Step-by-step:**

1. Parse GT file into list of `(timestamp, speaker, text)` tuples.
2. Parse transcript into list of `(start_time, speaker, text)` tuples.
3. For each GT utterance:
   a. Normalize GT text: lowercase, strip punctuation, expand numbers ("14" → "fourteen").
   b. For each transcript segment, normalize the same way.
   c. Compute word-level edit distance between normalized GT text and each segment text.
   d. WER = edit_distance / len(gt_words).
   e. Best match = segment with lowest WER.
   f. If best WER < 0.50 → MATCHED. Record the pairing.
   g. If best WER >= 0.50 → MISSED.
4. A transcript segment can match at most one GT utterance (greedy, best-first).

```
capture_rate = MATCHED / len(GT) × 100
```

**Concrete example from our E2E:**
- GT: `Alice "Good morning everyone. Let's review the quarterly results for the engineering team."`
- Transcript: `Alice (Guest) "Good morning, everyone. Let's review the quarterly results for the engineering team."`
- Normalized GT: `good morning everyone lets review the quarterly results for the engineering team`
- Normalized TX: `good morning everyone lets review the quarterly results for the engineering team`
- Edit distance: 0. WER: 0%. → MATCHED.

### 2. Speaker Attribution Accuracy

**Step-by-step:**

1. Take only MATCHED pairs from step 1.
2. For each pair, normalize speakers:
   a. Strip parenthetical suffixes: `"Alice (Guest)"` → `"Alice"`. Regex: `re.sub(r'\s*\(.*\)\s*$', '', speaker)`.
   b. Lowercase both.
3. Compare: `normalized_tx_speaker == normalized_gt_speaker`.

```
speaker_accuracy = CORRECT / MATCHED × 100
```

**What "correct" means precisely:**
- `"Alice (Guest)"` vs GT `"Alice"` → strip → `"alice"` == `"alice"` → CORRECT
- `"Bob (Guest)"` vs GT `"Alice"` → `"bob"` != `"alice"` → WRONG
- `"Unknown"` vs GT `"Alice"` → `"unknown"` != `"alice"` → WRONG

### 3. Word Error Rate (WER)

**Step-by-step:**

1. Take only MATCHED pairs.
2. For each pair:
   a. Normalize both texts: lowercase, strip punctuation, normalize whitespace.
   b. Number normalization: convert written numbers to digits in the GT side ("fourteen" → "14", "forty percent" → "40%") so they match Whisper output. Or: convert digits to words in the TX side. Either direction works as long as consistent.
   c. Split both into word lists.
   d. Compute Levenshtein distance at word level:
      - Substitution: word in GT replaced by different word in TX
      - Insertion: extra word in TX not in GT
      - Deletion: word in GT missing from TX
   e. `WER_segment = (S + I + D) / len(gt_words)`
3. `WER_overall = mean(WER_segment for all matched pairs)`

**Implementation:** Standard dynamic programming edit distance on word arrays. No external library required — ~20 lines of Python.

### 4. Timing Accuracy

**Step-by-step:**

This is the trickiest metric because GT timestamps are wall-clock (Unix epoch) and transcript timestamps are relative to recording start.

1. Compute `recording_start_epoch`:
   a. Take the first MATCHED pair: GT timestamp `gt_t` and segment `start_time` `seg_t`.
   b. `recording_start_epoch = gt_t - seg_t`
   c. This assumes the first utterance's timing is approximately correct — it anchors the alignment.

2. For each subsequent MATCHED pair:
   a. `expected_seg_start = gt_t - recording_start_epoch`
   b. `actual_seg_start = seg.start_time`
   c. `offset = |actual - expected|`

3. Count segments where `offset < 5.0` seconds.

```
timing_accuracy = within_5s / MATCHED × 100
```

**Why 5s tolerance:** TTS playback takes variable time. The `/speak` API returns immediately but the bot's TTS takes 1-3s to synthesize and begin playing. Plus Teams has ~1-2s caption delay. So 5s absorbs these system-level delays while catching gross misalignments.

### 5. Playback Accuracy

**Step-by-step:**

This is a manual/semi-automated check in the dashboard.

1. Open the dashboard at `http://localhost:3000/meetings/{meeting_id}`.
2. Verify the recording player is loaded and shows correct duration.
3. For each transcript segment visible in the UI:
   a. Note the segment's displayed `start_time`.
   b. Click the segment (or the play button on it).
   c. Observe where the audio player seeks to (the playback position indicator).
   d. `offset = |player_position - segment.start_time|`
4. Count segments where `offset < 3.0` seconds.

```
playback_accuracy = within_3s / total_segments × 100
```

**Automation path:** Could be automated via Playwright — open dashboard, query segment elements, click each, read `audioElement.currentTime` after seek. Not implemented yet.

## Confidence Gates — how each is validated

### Gate 1: Pipeline Works

Run these commands sequentially. ALL must succeed.

```bash
# 1. Recording exists in MinIO?
# Queries meeting-api for meeting data, checks recordings array
make -C tests check-recording MEETING_ID=$ID
# PASS: recordings array non-empty, status=completed
# FAIL: empty array or status != completed

# 2. Speaker events stored?
# Queries meeting.data.speaker_events
make -C tests check-speaker-events MEETING_ID=$ID
# PASS: speaker_events_count > 0
# FAIL: count = 0 or field missing

# 3. POST /transcribe succeeds?
make -C tests check-transcribe MEETING_ID=$ID
# PASS: HTTP 200, response has segment_count > 0
# FAIL: HTTP 4xx/5xx, or segment_count = 0

# 4. Segments in Postgres?
docker exec $(docker ps -q -f name=postgres) psql -U postgres -d vexa_restore -t -c \
  "SELECT count(*) FROM transcriptions WHERE meeting_id = $ID"
# PASS: count > 0
# FAIL: count = 0
```

### Gate 2: Quality Baseline

Requires Gate 1 passed. Run the scoring procedure above on a 2-speaker TTS meeting.

```bash
# 1. Export GT and transcript
cat data/raw/{dataset}/ground-truth.txt
docker exec $(docker ps -q -f name=postgres) psql -U postgres -d vexa_restore -t -c \
  "SELECT start_time, end_time, speaker, text FROM transcriptions WHERE meeting_id = $ID ORDER BY start_time"

# 2. Run scoring script
# python3 tests/score.py --gt data/raw/{dataset}/ground-truth.txt --meeting-id $ID

# 3. Check thresholds
# capture_rate >= 90%
# speaker_accuracy >= 70%
# WER <= 25%
# timing_accuracy >= 80%
```

Currently done manually by comparing the two outputs side-by-side.

### Gate 3: Quality Stress

Same scoring as Gate 2, but the dataset must include ALL of these scenarios:
- 3+ distinct speakers (different TTS voices)
- At least 2 rapid speaker changes (< 2s gap between utterances)
- At least 2 short utterances (< 3 words: "Yes", "OK", "Agreed")
- At least 1 long monologue (> 20s continuous speech from one speaker)
- At least 1 silence gap (> 10s pause between utterances)

The collection manifest declares which scenarios are included. Scoring reports per-scenario breakdown.

Thresholds are slightly relaxed vs Gate 2 (capture >= 80%, WER <= 30%) because edge cases are harder.

### Gate 4: Serving

```bash
# 1. GET /transcripts returns segments
curl -s "http://localhost:8056/transcripts/{platform}/{native_meeting_id}" \
  -H "X-API-Key: $TOKEN" | python3 -c "
import sys, json
data = json.load(sys.stdin)
segments = data.get('segments', [])
print(f'segment_count={len(segments)}')
# Compare to Postgres count
"
# PASS: segment_count matches Postgres count
# FAIL: segment_count = 0 or mismatch

# 2. Dashboard renders transcript
# Open http://localhost:3000/meetings/{meeting_id}
# Verify: all segments visible, speakers shown, text readable
# PASS: visual confirmation
# FAIL: blank page, missing segments, wrong speakers

# 3. Playback accuracy
# Click each segment in dashboard, measure seek offset (see metric 5 above)
# PASS: offset < 3s for >= 80% of segments
# FAIL: offset > 3s for > 20% of segments
```

## Scoring output format

After each run, report:

```
=== Post-Meeting Transcription Score ===
Meeting: {id} | Platform: {platform} | Speakers: {N}
Dataset: {dataset_id}

Capture:  {matched}/{total} ({rate}%)  threshold: >=90%  {PASS/FAIL}
Speaker:  {correct}/{matched} ({rate}%)  threshold: >=70%  {PASS/FAIL}
WER:      {avg}%  threshold: <=25%  {PASS/FAIL}
Timing:   {within_5s}/{matched} ({rate}%)  threshold: >=80%  {PASS/FAIL}
Playback: {within_3s}/{total} ({rate}%)  threshold: >=80%  {PASS/FAIL/NOT TESTED}

Per-segment detail:
  #1  GT: Alice "Good morning..."  TX: Alice (Guest) "Good morning..."  speaker=OK  wer=0%  offset=0.3s
  #2  GT: Bob "Thanks..."         TX: Bob (Guest) "Thanks..."          speaker=OK  wer=2%  offset=0.5s
  ...

Gate 1: {PASS/FAIL}
Gate 2: {PASS/FAIL}
Gate 3: {PASS/FAIL/NOT TESTED}
Gate 4: {PASS/FAIL/NOT TESTED}
```
