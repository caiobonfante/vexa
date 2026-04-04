# Mission: First-Principles Post-Meeting Transcription Validation

Focus: post-meeting-transcription
Problem: Last validation was 2026-03-23, dashboard items untested (certainty 30%), timestamp alignment never verified systematically. Previous results are stale — trust nothing, verify everything from scratch.
Target: Fresh meeting → recording → speakers → transcription → dashboard playback, all verified end-to-end with timestamp alignment evidence.
Stop-when: All DoD items pass OR 10 iterations.
Constraint: Use existing infrastructure. Do NOT trust previous test results.

## DoD (Definition of Done)

### 1. Meeting recorded
- [ ] Bot joins a live Google Meet via CDP
- [ ] Bot records audio (webm)
- [ ] Recording uploaded to MinIO — verify with `mc ls` or MinIO API
- [ ] Recording is downloadable and playable (non-zero duration, valid audio)

### 2. Speakers collected
- [ ] Speaker SPEAKER_START/SPEAKER_END events captured during meeting
- [ ] Events persisted in `meeting.data` JSONB in Postgres
- [ ] Query Postgres directly: events have timestamps, speaker names, and are ordered correctly
- [ ] At least 2 distinct speakers detected

### 3. Speakers mapped via transcription
- [ ] `POST /meetings/{id}/transcribe` through api-gateway succeeds
- [ ] Whisper produces segments with text and timestamps
- [ ] Speaker mapping assigns correct names to segments (not all "Unknown")
- [ ] Speaker accuracy ≥ 70% (compare mapped names to known ground truth)
- [ ] `GET /transcripts/{meeting_id}` returns all segments with speaker labels

### 4. Dashboard works end-to-end
- [ ] Dashboard at :3001 loads meeting list, shows the test meeting
- [ ] Clicking the meeting shows transcript with speaker-labeled segments
- [ ] Audio player loads and plays the recording
- [ ] Clicking a segment seeks audio to that segment's timestamp
- [ ] Seek lands within 3 seconds of the correct position

### 5. Timestamps aligned in all situations
This is the critical verification — recording time, segment times, and playback must be consistent:
- [ ] Segment `start_time` / `end_time` are relative to recording start (not wall clock)
- [ ] First segment starts near 0s (not minutes into the recording)
- [ ] Last segment ends before or at recording duration
- [ ] No gaps > 30s between consecutive segments where speech was happening
- [ ] Clicking early segment → plays early audio. Clicking late segment → plays late audio (monotonic).
- [ ] `duration_seconds` on the recording is NOT null (known issue — must be fixed or worked around)
- [ ] If meeting has pauses, segments after the pause still align to correct audio position

## Verification Method

**Do not verify by reading code.** Verify by:
1. Running a real meeting with at least 2 speakers (use TTS bots or manual)
2. Querying Postgres for raw data (events, segments, recordings)
3. Calling APIs through api-gateway (not internal services)
4. Opening the dashboard in a browser (via CDP/VNC)
5. Comparing segment timestamps against actual audio content

## Infrastructure (pre-check required)

```
api-gateway      :8056   must be healthy
meeting-api      :8080   must be healthy (includes meeting + collector)
transcription-lb :8085   must be healthy
postgres         :5438   must be accessible
minio            :9000   must be accessible
dashboard        :3001   must be accessible (container: front)
tts-service      :8002   needed if using TTS bots
browser session          at least one CDP endpoint for bot
```

## Known Risks

- `duration_seconds=null` may break seek — if so, must fix before dashboard items can pass
- Dashboard container (`front`) is 13 days old — may need rebuild if code changed
- Short utterances (1 word) get "Unknown" speaker — acceptable if overall accuracy ≥ 70%
- Video playback (not audio) may need ffmpeg in container — separate from this mission
