# WAV Pipeline Test
Confidence: 80 — 1 confirmed segment from 6s WAV, confirmation logic works post-fix. Tested 2026-03-24.
Command: `cd services/vexa-bot/core && npx ts-node src/services/speaker-streams.wav-test.ts <wav-file>`
Output: confirmed segments to stdout with speaker, text, timestamps. Count of segments = quality signal.
Needs:
  - transcription-service running (check: `curl -s http://localhost:8083/health`)
  - WAV file: 16kHz mono PCM. Use `services/transcription-service/tests/test_audio.wav` (6s) or generate longer with generate-test-audio tool.
  - node_modules installed in services/vexa-bot/core
  - env: TRANSCRIPTION_URL=http://localhost:8083/v1/audio/transcriptions
Dead ends: none known
