# Post-Meeting Transcription

> **Confidence: 0** — RESET after architecture refactoring. Pipeline code moved to meeting-api/collector. Import paths changed. Needs re-validation.
> **Tested:** Recording to MinIO, speaker event collection, Whisper transcription, speaker mapping via overlap algorithm, segment persistence to Postgres.
> **Not tested:** Dashboard playback offset (known ~2-5s bug), re-transcription (returns 409), retry on failure, accuracy with 3+ speakers.
> **Contributions welcome:** Dashboard playback seek fix, re-transcription support, multi-speaker accuracy testing.

## Why

Not all users want realtime transcription. Some just want recording + speaker events during the meeting, then high-quality transcription on demand afterward. Post-meeting transcription is cheaper (one Whisper pass over the full recording) and more reliable (no streaming edge cases, full audio context).

This is a basic use case for meeting bots — record, then transcribe.

**Downstream:** Transcription completion fires `transcript.ready` webhook → can trigger agent containers for summarization, entity extraction, or any post-meeting automation via scheduler callbacks.

## What

User triggers transcription after a completed meeting. The system downloads the recording from storage, runs Whisper on the full audio, maps speakers using speaker events collected during the meeting, and writes segments to the database. The dashboard shows the result with click-to-play (segment click seeks the recording to that timestamp).

### Components

- **bot-manager**: orchestrates the full flow — downloads recording, calls transcription service, maps speakers, writes to Postgres
- **transcription-service**: Whisper API (`/v1/audio/transcriptions`) — transcribes the full recording
- **vexa-bot**: during meeting, records audio (uploads to MinIO) and collects speaker events (sent on exit)
- **api-gateway**: proxies `POST /meetings/{id}/transcribe` to bot-manager, serves transcript via `GET /transcripts`
- **dashboard**: renders transcript segments with click-to-play recording playback

### Data flow

```
[During meeting]
  bot records audio → uploads to MinIO (recordings/{user_id}/{recording_id}/{session_uid}.{format})
  bot accumulates speaker_events in memory (SPEAKER_START/SPEAKER_END per participant)
  bot exits → sends speaker_events to bot-manager via /status_change callback
  bot-manager stores speaker_events in meeting.data JSONB

[After meeting — user triggers]
  POST /meetings/{id}/transcribe
    → bot-manager downloads recording from MinIO
    → bot-manager sends recording to transcription-service /v1/audio/transcriptions
    → Whisper returns segments [{start, end, text}, ...]
    → bot-manager runs _map_speakers_to_segments(speaker_events, segments)
       (overlap algorithm: each segment assigned to speaker with most time overlap)
    → bot-manager writes Transcription rows to Postgres
    → bot-manager sets meeting.data.transcribed_at

[Dashboard]
  GET /transcripts/{platform}/{native_meeting_id} → returns segments with speakers
  Click segment → seeks recording playback to segment.start_time
```

### Key behaviors

- Transcription is user-triggered via API, not automatic
- Uses full recording for better context vs real-time chunked processing
- Speaker mapping via timestamp overlap between speaker events and Whisper segments
- 409 if transcription already exists (no re-run yet — multiple versions is a nice-to-have)
- Dashboard playback: click segment to play recording at that position (currently has ~2-5s offset bug)

### Data stages

| Stage | Contents | Produced by | Consumed by |
|-------|----------|-------------|-------------|
| **raw** | Recording (webm) + speaker_events in meeting.data | Bot during meeting | Deferred transcription |
| **core** | Whisper segments mapped to speakers | bot-manager transcribe endpoint | Postgres |
| **rendered** | Transcript via REST + dashboard playback | api-gateway + dashboard | Users |

Note: no dataset directories exist yet. `data/raw/`, `data/core/`, and `data/rendered/` are populated on demand during collection runs.

### Configuration

| Env var | Default | Where | Purpose |
|---------|---------|-------|---------|
| `TRANSCRIPTION_GATEWAY_URL` | (empty) | bot-manager | Whisper endpoint (preferred, falls back to `TRANSCRIPTION_SERVICE_URL`) |
| `TRANSCRIPTION_SERVICE_URL` | `http://vexa-transcription-gateway:8084` | bot-manager | Whisper endpoint (fallback if `TRANSCRIPTION_GATEWAY_URL` unset) |
| `MINIO_ENDPOINT` | `minio:9000` | bot-manager | Recording storage |
| `MINIO_BUCKET` | `vexa-recordings` | bot-manager | Recording bucket |

## How

### Test procedure

1. Start compose stack
2. Host a meeting with TTS bots (known speakers, scripted utterances)
3. Let meeting complete — verify recording uploaded + speaker_events stored
4. Call `POST /meetings/{meeting_id}/transcribe`
5. Verify `GET /transcripts` returns segments with correct speakers
6. Verify dashboard playback: click segment seeks to correct position
7. Score speaker attribution accuracy against ground truth (target: >=70%)

### Known limitations

- No re-transcription (409 if already transcribed) — multiple versions is a nice-to-have
- Speaker mapping accuracy depends on speaker event quality (DOM-based detection)
- Dashboard playback has ~2-5s offset (MediaRecorder vs SegmentPublisher start time drift)
- No retry on transcription failure
