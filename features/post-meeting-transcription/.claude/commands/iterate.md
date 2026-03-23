# /iterate — Sandbox iteration for post-meeting transcription

You are in **Stage 2: SANDBOX ITERATION** for the post-meeting-transcription feature.

Read the generic stage protocol first: `/.claude/commands/iterate.md`

## What iteration looks like for this feature

Unlike realtime-transcription (which replays audio through the pipeline at real-time speed), post-meeting iteration is:

1. **Fast** — no real-time audio processing. The deferred transcription endpoint processes a recording file (webm/wav) and returns segments.
2. **Deterministic** — same recording + same speaker_events = same output (no timing-dependent behavior).
3. **API-driven** — you can re-trigger transcription on the same recording (after clearing previous results).

### Iteration loop

```
1. Clear existing transcription for meeting (DELETE transcriptions WHERE meeting_id = X)
2. Optionally modify _map_speakers_to_segments() or transcription params
3. Re-run POST /meetings/{id}/transcribe
4. Score output against ground truth
5. Compare to previous iteration
6. Repeat
```

### Key source files to modify

| Component | File | What it does |
|-----------|------|-------------|
| Speaker mapping | `services/bot-manager/app/main.py:_map_speakers_to_segments` | Overlap-based speaker attribution |
| Transcription endpoint | `services/bot-manager/app/main.py:transcribe_meeting_recording` | Full deferred flow |
| Speaker event collection | `services/vexa-bot/core/src/index.ts:performGracefulLeave` | How events are gathered on exit |
| Recording upload | `services/vexa-bot/core/src/services/recording.ts` | Audio recording + upload |
| Dashboard playback | `services/dashboard/src/app/meetings/[id]/page.tsx` | Segment click → audio seek |
| Audio player | `services/dashboard/src/components/recording/audio-player.tsx` | Multi-fragment playback |

### Common root causes and where to look

| Symptom | Root cause area | Where |
|---------|----------------|-------|
| All speakers "Unknown" | speaker_events empty or not persisted | bot exit flow → bot-manager callback |
| Wrong speaker on segment | Overlap algorithm picks wrong speaker | `_map_speakers_to_segments` logic |
| Missing recording | Upload URL not configured or upload failed | bot config + recording.ts |
| 502 from transcription | Transcription service unreachable | TRANSCRIPTION_GATEWAY_URL config |
| Playback offset 2-5s | MediaRecorder/SegmentPublisher start drift | dashboard page.tsx time mapping |
| 409 on re-transcribe | Previous transcription exists | Need to clear transcriptions table |

### How to clear transcription for re-run

```sql
-- Connect to Postgres
DELETE FROM transcriptions WHERE meeting_id = {MEETING_ID};
-- Also clear the meeting.data flags
UPDATE meetings SET data = data - 'transcribed_at' - 'transcription_language' WHERE id = {MEETING_ID};
UPDATE meetings SET data = jsonb_set(data, '{transcribe_enabled}', 'false') WHERE id = {MEETING_ID};
```

Then re-run `POST /meetings/{id}/transcribe`.

### Scoring

For each ground truth utterance, check:
1. **Found?** — is there a segment with matching text (fuzzy match, WER < 30%)?
2. **Speaker correct?** — does the segment's speaker match the ground truth speaker?
3. **Timing reasonable?** — is segment.start within 5s of the ground truth timestamp?

Report:
```
Iteration {N}:
  Segments: {found}/{total} ({%} captured)
  Speaker accuracy: {correct}/{found} ({%})
  Fix: {description}
  Status: {iterating | plateau | target met}
```

### When you've hit a plateau

If speaker mapping is stuck and remaining errors are:
- **Overlapping speech** → speaker events don't capture simultaneous speakers well → `/expand`
- **Short utterances** → Whisper merges short utterances into adjacent segments → `/expand`
- **Many speakers** → overlap algorithm gets confused with >3 speakers → `/expand`
- **Recording quality** → audio too poor for Whisper → out of scope for this feature

### Dashboard playback iteration

For playback bugs, iterate by:
1. Note the segment start_time and the actual audio position when clicked
2. Measure the offset
3. Trace through the time mapping code in `page.tsx`
4. Fix the mapping logic
5. Verify by clicking multiple segments across the timeline
