# Replay Pipeline
Confidence: 70 — worked during development, not run since confirmation fix.
Command: `cd features/realtime-transcription/tests && make play-replay DATASET=teams-3sp-collection`
Actual: `cd services/vexa-bot/core && npx ts-node src/services/production-replay.test.ts`
Output: captured utterances, speaker accuracy, scoring vs ground truth.
Needs:
  - transcription-service running
  - dataset in features/realtime-transcription/data/raw/{DATASET}/ with audio files + events.txt + ground-truth.txt
  - node_modules installed in services/vexa-bot/core
  - env: TRANSCRIPTION_URL, DATASET
Data status: data/raw/ directory is EMPTY in repo — datasets were collected but not committed (audio files gitignored). Must regenerate via generate-test-audio or run a collection.
Dead ends: replay with invalid meeting IDs causes silent failure (no error, just 0 segments). Must use valid 13-digit numeric IDs.
