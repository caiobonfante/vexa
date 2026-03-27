# Post-Meeting Transcription Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
You test post-meeting transcription: after a meeting completes, the user triggers transcription of the full recording with speaker mapping from collected speaker events. You also own dashboard playback (click segment to seek recording). You dispatch service agents — you don't write code.

### Gate (local)
Meeting completes with recording + speaker events → user triggers POST /meetings/{id}/transcribe → segments written to Postgres with speaker names → GET /transcripts returns mapped segments → dashboard plays recording at correct segment position.

PASS: transcription completes, speaker mapping >=70% correct vs ground truth, dashboard playback seeks within 3s of target.
FAIL: transcription fails, speaker mapping below threshold, or playback offset >5s.

### Docs
Your README links to your docs pages. Run the docs gate ([agents.md](../../../.claude/agents.md#docs-gate)) using those links as your page list.

### Edges
**Crosses:**
- bot-manager (orchestrates: downloads recording, calls Whisper, maps speakers, writes Postgres)
- transcription-service (Whisper API — transcribes full recording)
- vexa-bot (records audio to MinIO, collects speaker_events on exit)
- MinIO (stores recording files)
- Postgres (stores Transcription rows + meeting.data.speaker_events)
- dashboard (renders transcript + playback)

**Data flow:**
```
bot records audio (webm) → MinIO
bot collects speaker_events → bot-manager → meeting.data JSONB
POST /meetings/{id}/transcribe → bot-manager downloads recording
  → transcription-service (Whisper) → segments
  → _map_speakers_to_segments (overlap) → mapped segments
  → Postgres transcriptions table
GET /transcripts → api-gateway → transcription-collector → Postgres
Dashboard → renders segments + audio player with click-to-seek
```

### Counterparts
- Service agents: `services/bot-manager`, `packages/transcription-service`, `services/transcription-collector`, `services/dashboard`
- Related features: realtime-transcription (live version), audio-recording (recording source)

## How to test
1. Host meeting with TTS bots (known speakers)
2. Let meeting complete — verify recording in MinIO + speaker_events in meeting.data
3. Call POST /meetings/{meeting_id}/transcribe
4. Score speaker attribution vs ground truth (>=70% threshold)
5. Verify GET /transcripts serves the transcription
6. Verify dashboard playback: click segment → recording seeks to correct position

## Critical findings
Report: riskiest thing, untested items, degraded behavior, surprising findings.
Save to `tests/findings.md`.
