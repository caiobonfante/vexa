# Delivery Tests — YouTube Audio Pipeline

## Why

TTS-generated test audio has clean gaps, uniform pacing, and no natural speech artifacts. Bugs that appear with real human speech (overlaps, hesitations, varying pace, accents) are invisible. We need real speech flowing through the full pipeline — capture, transcription, attribution, delivery, rendering — with automated validation at every stage.

## What

Take a YouTube video (interview, meeting, panel), extract per-speaker audio segments, play them from separate bots into a live meeting, capture the pipeline output, and validate against ground truth — then replay the core data through delivery tick by tick.

```
YouTube video
  --> yt-dlp download (mono audio)
  --> Whisper offline transcription (segments with timestamps)
  --> AI speaker assignment (analytical diarization, segment by segment)
  = GROUND TRUTH: { speaker, text, start, end }[] + per-speaker audio files

Per-speaker audio files
  --> N bots join meeting, each plays their speaker's segments
  --> recorder bot captures pipeline output
  = CORE DATA: transcript ticks (confirmed + pending per speaker)

CORE DATA vs GROUND TRUTH
  = LEFT-SIDE VALIDATION (capture accuracy, speaker attribution, text accuracy)

CORE DATA --> replay through delivery pipeline tick by tick
  = RIGHT-SIDE VALIDATION (WS/REST/dashboard rendering correctness)
```

## Pipeline steps

### Step 1: Download YouTube audio

```bash
yt-dlp -x --audio-format wav -o "source.wav" "$YOUTUBE_URL"
ffmpeg -i source.wav -ar 16000 -ac 1 source-16k.wav
```

### Step 2: Offline Whisper transcription

Full-file, best quality, with word timestamps for tighter cuts.

```bash
curl -X POST $TRANSCRIPTION_URL \
  -H "Authorization: Bearer $TRANSCRIPTION_TOKEN" \
  -F "file=@source-16k.wav" \
  -F "model=large-v3-turbo" \
  -F "timestamp_granularities=segment" \
  -F "response_format=verbose_json" \
  > whisper-output.json
```

Output: segments with `{ text, start, end }`.

### Step 3: AI speaker assignment

Analytical diarization — assign a speaker name to each Whisper segment based on content, context, and conversational flow. This is an AI task (Claude), not a signal processing task.

Rules:
- Each segment gets exactly one speaker name
- Names are arbitrary labels (Speaker-A, Speaker-B, or real names if identifiable)
- Doesn't need to be perfect — the ground truth is "what each bot plays," not the original speaker identity
- Overlapping speech in the source audio is an accepted limitation — the segment goes to one bot and contains both voices

Output: `ground-truth.json` — array of `{ speaker, text, start, end }`.

### Step 4: Split audio per speaker

Cut the source audio into per-segment files using Whisper timestamps.

```bash
# For each segment in ground-truth.json:
ffmpeg -ss {start} -to {end} -i source-16k.wav segment-{N}-{speaker}.wav
```

Group by speaker into per-speaker playlists with timing metadata.

### Step 5: Play from bots into live meeting

- Create a live meeting (Google Meet or Teams)
- Launch N speaker bots + 1 recorder bot
- Each bot has a playlist: play segment 1 at offset 0s, segment 2 at offset 12s, etc.
- Bots play independently — no cross-bot synchronization needed
- Ground truth is "what each bot played," not original video timing
- Recorder bot captures pipeline output

Uses existing `TTSPlaybackService.playFile()` — plays arbitrary audio via PulseAudio `tts_sink`.

### Step 6: Validate core data vs ground truth

Compare pipeline output against ground truth:
- **Text accuracy:** fuzzy match (keyword overlap, allowing for Whisper streaming vs offline differences)
- **Speaker attribution:** each confirmed segment attributed to the correct bot/speaker
- **Completeness:** no dropped utterances (within platform limitations)
- **Timing:** segments appear in correct chronological order

Uses existing scoring from `production-replay.test.ts` (keyword matching + time-proximity tiebreaker).

### Step 7: Replay core data through delivery

Feed core ticks through delivery pipeline, validate rendered result tick by tick.

Uses existing `replay-delivery-test.js`:
- Per-tick invariants (monotonic confirmed, no phantoms, progressive coverage)
- WS/REST consistency after immutability wait
- Dashboard state model validation

## Confidence table

| Component | Confidence | Reasoning | Accepted limitations |
|-----------|-----------|-----------|---------------------|
| YouTube download | 95% | yt-dlp + ffmpeg, battle-tested | None |
| Offline Whisper transcription | 90% | Already used in existing tests | None |
| AI speaker assignment | 85% | Segment-by-segment content analysis; errors are acceptable because GT = what bot plays | Occasional misattribution doesn't break the test |
| Audio splitting (ffmpeg) | 90% | Exact timestamp cuts, reliable | Overlap in source audio — one bot plays both voices. Accepted. |
| Per-bot audio playback | 85% | TTSPlaybackService.playFile() exists, PulseAudio routing proven | None |
| Multi-bot playlist playback | 85% | Each bot plays its playlist independently; no sync needed; playFile() proven | None |
| Pipeline processing | 85% | Proven with TTS datasets | Meeting codec degrades audio vs offline Whisper |
| GT comparison (scoring) | 80% | Existing fuzzy matching works; real speech has more ambiguity than TTS | Streaming vs offline Whisper will differ |
| Delivery replay validation | 90% | replay-delivery-test.js is proven | None |

**Overall: 80%** (bottleneck: GT comparison scoring with real speech ambiguity)

## Accepted limitations

1. **Overlapping speech:** When two speakers talk simultaneously in the source video, the segment goes to one bot. That bot plays both voices. The recorder hears one source with two voices. This doesn't break the test — it tests how the pipeline handles messy audio.

2. **Audio quality degradation:** YouTube audio re-encoded through a meeting codec will produce different Whisper results than offline transcription of the original. Fuzzy matching accounts for this.

3. **Playback timing:** Bots play independently so the conversation won't sound exactly like the original video. Doesn't affect validation — ground truth is per-bot, not per-original-timestamp.

## Dataset structure

```
data/raw/{dataset}/
  source-16k.wav              # Full YouTube audio (16kHz mono)
  whisper-output.json         # Offline Whisper segments
  ground-truth.json           # Speaker-assigned segments
  audio/
    speaker-a/
      00-segment.wav          # Cut audio for each segment
      01-segment.wav
      playlist.json           # { segments: [{ file, start, end }] }
    speaker-b/
      ...

data/core/{dataset}/
  transcript.jsonl            # Pipeline output (one tick per line)
```

## What to build

| Component | Exists? | Work needed |
|-----------|---------|-------------|
| YouTube download + Whisper | Partial | Script to automate download + offline transcription |
| AI speaker assignment | No | Script/prompt that takes Whisper segments, outputs speaker-labeled GT |
| Audio splitter | No | Script: ground-truth.json + source.wav --> per-speaker segment files |
| Bot playlist player | No | Extend speak_audio to accept a playlist with offsets |
| Left-side scorer | Partial | Adapt production-replay scoring for YouTube GT format |
| Right-side replay | Yes | replay-delivery-test.js works as-is with core data |
