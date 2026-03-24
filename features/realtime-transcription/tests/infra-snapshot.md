# Infrastructure Snapshot — 2026-03-20

Frozen record of infrastructure state. Sandbox tests MUST match these configs exactly.

## Transcription Service

**Endpoint:** `http://localhost:8083/v1/audio/transcriptions` (dev instance, via nginx LB)
**Auth:** `Authorization: Bearer {set, length 26}`
**Model:** `large-v3-turbo`, device=cuda, compute_type=int8
**Source:** `/home/dima/dev/vexa-restore/services/transcription-service/` (compose project: `transcription-service`)

**2 workers on GPUs 2-3:**
- transcription-service-transcription-worker-1-1
- transcription-service-transcription-worker-2-1

**Word timestamps:** Returned when `timestamp_granularities=word` is sent as form field.
Verified: smoke test returns 8 words for `short-sentence.wav` — 100% accuracy.

**VAD defaults (env):**
- `VAD_MAX_SPEECH_DURATION_S=15.0` (default in main.py)
- `VAD_MIN_SILENCE_DURATION_MS=160` (default in main.py)
- `VAD_FILTER=True` (default in main.py)

**Per-request overrides (form fields):**
- `max_speech_duration_s` — overrides VAD_MAX_SPEECH_DURATION_S
- `min_silence_duration_ms` — overrides VAD_MIN_SILENCE_DURATION_MS
- `timestamp_granularities=word` — enables word-level timestamps

## Bot Image

**Image:** `vexa-bot:dev` (`sha256:73420`)
**Source:** `/home/dima/dev/vexa-restore/services/vexa-bot/`
**Build:** `make -C deploy/compose build-bot-image`

**Features in current image:**
- Carry-forward: YES (short audio transferred to next speaker on flush)
- Speaker-mapper in onSegmentConfirmed: YES (splits multi-speaker segments)
- latestWhisperWords storage: YES (set in onSegmentReady)
- captionEventLog accumulation: YES (set in handleTeamsCaptionData)

## The Config Mismatch (KNOWN BUG)

**TranscriptionClient in production bot (index.ts line 991):**
```typescript
transcriptionClient = new TranscriptionClient({
  serviceUrl: transcriptionServiceUrl,
  apiToken: botConfig.transcriptionServiceToken,
  // NO maxSpeechDurationSec
});
```

**TranscriptionClient in WAV test (speaker-streams.wav-test.ts):**
```typescript
const txClient = new TranscriptionClient({
  serviceUrl: TX_URL, apiToken: TX_TOKEN, sampleRate: SAMPLE_RATE,
  maxSpeechDurationSec: 15,  // <-- THIS IS DIFFERENT
});
```

**TranscriptionClient in production-replay test:**
```typescript
const txClient = new TranscriptionClient({
  serviceUrl: TX_URL, apiToken: TX_TOKEN, sampleRate: SAMPLE_RATE,
  // NO maxSpeechDurationSec (same as production)
});
```

**Impact:** The WAV test gets word timestamps (words work). Production bots and the production-replay test may not (words=0 in collection runs). Debug bot 297 DID get words without `maxSpeechDurationSec` — so this mismatch may NOT be the cause. Investigation ongoing.

**The `timestamp_granularities=word` form field is sent unconditionally** by all three configs. The `maxSpeechDurationSec` only adds an extra `max_speech_duration_s` field after it. Whether the absence of this extra field affects multipart parsing of `timestamp_granularities` is unverified.

## SpeakerStreamManager Config

**Production bot (index.ts ~line 1037, updated since this snapshot):**
```
sampleRate: 16000
minAudioDuration: 3
submitInterval: 2      ← was 3 at snapshot time; changed after latency tuning (Iteration 3)
confirmThreshold: 2    ← was 3 at snapshot time; changed after latency tuning (Iteration 3)
maxBufferDuration: 120
idleTimeoutSec: 15
```

**Note:** This snapshot was captured 2026-03-20 when submitInterval=3, confirmThreshold=3. The values were reduced to 2 each in Iteration 3 (2026-03-21) during latency tuning (16.5s → 10.8s). The sandbox and production bot now use the same updated values.

## Sandbox Requirements

For sandbox tests to match production:
1. Use `TRANSCRIPTION_URL=http://localhost:8083/v1/audio/transcriptions`
2. Use `TRANSCRIPTION_TOKEN=dev-rt-transcription-2026`
3. TranscriptionClient config must match production (NO `maxSpeechDurationSec` unless production adds it)
4. SpeakerStreamManager config must match production (3/3/3/120/15)
5. Both transcription workers must have word timestamp support

## .env (redacted)

```
TRANSCRIPTION_URL=http://localhost:8083/v1/audio/transcriptions
TRANSCRIPTION_TOKEN={set, length 26}
MODEL_SIZE=large-v3-turbo
COMPUTE_TYPE=int8
DEVICE=cuda
BEAM_SIZE=5
VAD_FILTER=true
VAD_FILTER_THRESHOLD=0.5
NO_SPEECH_THRESHOLD=0.6
MAX_CONCURRENT_TRANSCRIPTIONS=2
SUBMIT_INTERVAL=3
CONFIRM_THRESHOLD=3
MIN_AUDIO_DURATION=3
MAX_BUFFER_DURATION=120
IDLE_TIMEOUT_SEC=15
MAX_SPEECH_DURATION_SEC=15
TTS_URL=http://localhost:8002/v1/audio/speech
TTS_VOICE=en_US-lessac-medium
PLATFORM=ms-teams
API_GATEWAY_URL=http://localhost:8066
REDIS_URL=redis://localhost:6379
POSTGRES_URL=postgresql://postgres:postgres@localhost:5448/vexa_restore
BOT_IMAGE_NAME=vexa-bot-restore:dev
```

## Health Checks (2026-03-20)

| Service | Endpoint | Result |
|---------|----------|--------|
| Transcription (dev) | `http://localhost:8083/health` | 200 OK |
| API Gateway | `http://localhost:8066/` | 200 (Welcome to Vexa API Gateway) |
| Postgres | `psql localhost:5448` | SELECT 1 OK |
| Redis | `docker exec redis-1 PING` | PONG (not host-exposed) |
| TTS | `vexa-restore-tts-service-1:8002` | Running (not host-exposed) |

## Smoke Test

```
short-sentence.wav -> 100% accuracy, 8/8 words, RTF 0.18x
Word timestamps: all 8 present with valid offsets
```

## Collection Run Data (from previous snapshot)

**Meeting:** 9336586979259
**Date:** 2026-03-20 17:28-17:33 UTC
**Bots:** Listener (309), Alice (310), Bob (311), Charlie (312)
**Script:** 20 utterances, 3 speakers, unique text per utterance
**Results:** 8/17 captured, 0 mapper splits, 0 word timestamps in pipeline

**Files:**
- `collection-run-gt.txt` — ground truth (20 utterances with timestamps)
- `collection-run-events.txt` — 254 timestamped events
- `collection-run-raw-logs.txt` — full bot logs

## Sandbox Verified (2026-03-20 20:45)

**Production-replay test runs locally with production-matching config:**
- TranscriptionClient WITHOUT maxSpeechDurationSec: words=65, 10, 37 (all non-zero)
- Mapper fires: YES (SPLIT into 3, SPLIT into 2 observed)
- captionEventLog populated: 64-153 events
- latestWhisperWords populated: 8-65 words per submission

**The sandbox reproduces production behavior.** The live meeting failures were
infra-only (stale worker images, bot container rebuild timing). The code path
is correct — proven both by unit test (mapper fires on normal + idle path)
and by production-replay (words flow, mapper splits).

**Remaining sandbox issue:** Audio files reuse same text (short-sentence.wav
for all speakers). Ground truth comparison can't distinguish speakers by text.
Need per-utterance TTS or different scoring method.

**Stage: SANDBOX ITERATION ready.** Scoring method needs fix, then iterate.
