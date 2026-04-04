# Mission: Validate Real-Time Google Meet Transcription

Focus: realtime-transcription/google-meet
Problem: No recent validated E2E evidence. There's a bot in a live meeting (meeting-11) but all 34 whisper calls failed, 0 confirmed segments. Need to diagnose, fix, and run the full E2E test with scoring.
Target: Run E2E test with TTS bots speaking scripted utterances, score ≥90 (speaker accuracy ≥90%, completeness ≥80%, WER ≤30%).
Stop-when: E2E test passes with stored evidence OR 10 iterations.
Constraint: Use existing infrastructure. Tokens from `vexa` DB via .env.

## DoD (Definition of Done)

1. Bot joins Google Meet and produces confirmed transcription segments
2. E2E test script runs with TTS bots (Alice, Bob, Charlie) speaking ground truth
3. Segments appear in Postgres with correct speaker attribution
4. Scorer output: speaker accuracy ≥90%, completeness ≥80%, WER ≤30%
5. Results stored in `features/realtime-transcription/google-meet/tests/e2e/results/`

## Current State (2026-03-28)

### Infrastructure (verified)
- transcription-service: healthy (CUDA, large-v3-turbo, port 8085)
- api-gateway: healthy (port 8056)
- meeting-api: healthy (port 8080)
- runtime-api: healthy (port 8090)
- Redis: healthy (6379)
- Postgres: healthy (5438)
- TTS service: healthy (port 8002)

### Active bot (meeting-11-0ba90cfb)
- In Google Meet with Dmitriy Grankin
- CDP exposed at localhost:33034
- **Problem:** 34 whisper calls ALL failed, 0 confirmed segments
- Streams silent for 800+s (but speaker detection fires for Dmitriy Grankin)
- VAD: 317 checked, 240 rejected

### Root Cause (diagnosed during PLAN)
1. **Whisper 401 errors** — `TRANSCRIPTION_SERVICE_TOKEN` was empty because bot was spawned before meeting-api had it configured
2. **TRANSCRIPTION_SERVICE_URL was wrong** — `.env` had `http://transcription-service:80/...` but `transcription-service` doesn't resolve on compose network. Fixed to `http://transcription-lb/...`
3. **Both issues now fixed** — meeting-api recreated with correct URL (`http://transcription-lb/v1/audio/transcriptions`) and token (`32c59b9f654f1b6e376c6f020d79897d`)
4. **Broken bot (meeting-11) stopped** — need new bot

### Test Script Issues (from Teams mission — likely same)
1. Port hardcoded as 5448 — correct (Postgres host port)
2. Database hardcoded as `vexa_restore` — may need to be `vexa` (check .env tokens)
3. Token defaults in script are stale — use .env tokens
4. REDIS_URL hardcoded — needs password

### DELIVER Must Do
1. Fix test script config (DB, tokens, Redis URL) to match current infra
2. Create a Google Meet (via CDP or manually)
3. Run the E2E test
4. If failures, diagnose and fix
5. Store scoring results
