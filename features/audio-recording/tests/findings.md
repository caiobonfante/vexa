# Audio Recording Test Findings

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Bot captures audio | 0 | Not tested | — | Start bot with recording, verify MediaRecorder active |
| Recording uploaded to storage | 0 | Not tested | — | Check MinIO/S3 for recording file after meeting |
| Metadata persisted | 0 | Not tested | — | Query Postgres for recording metadata entry |
| Download endpoint works | 0 | Not tested | — | GET /recordings/{id}/media/{fid}/download returns 200 |
| Downloaded file playable | 0 | Not tested | — | Download file, verify valid audio format and playback |
| Recording-only mode | 0 | Not tested | — | Start bot in recording-only mode, verify no transcription |
