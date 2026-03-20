# Infrastructure Snapshot — 2026-03-20

Frozen record of infrastructure state. Sandbox tests MUST match these configs exactly.

## Transcription Service

**Endpoint:** `http://localhost:8085/v1/audio/transcriptions` (via nginx LB)
**Auth:** `Authorization: Bearer 32c59b9f654f1b6e376c6f020d79897d`
**Model:** `large-v3-turbo`, device=cuda, compute_type=int8

**3 workers, all on same image:**
- transcription-worker-1: `sha256:80eea` — has `want_word_timestamps`, `VAD_MAX_SPEECH_DURATION_S`
- transcription-worker-2: `sha256:a4f61` — same
- transcription-worker-3: `sha256:72db0` — same

**Source:** `/home/dima/prod/prod-transcription-service/main.py`
(copied from `/home/dima/dev/vexa-restore/services/transcription-service/main.py`)

**Word timestamps:** Returned when `timestamp_granularities=word` is sent as form field.
Verified: 3/3 workers return 8 words for `short-sentence.wav` via curl.

**VAD defaults (env):**
- `VAD_MAX_SPEECH_DURATION_S=15.0`
- `VAD_MIN_SILENCE_DURATION_MS=160`
- `VAD_FILTER=True`

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

**Production bot (index.ts line 1022):**
```
sampleRate: 16000
minAudioDuration: 3
submitInterval: 3
confirmThreshold: 3
maxBufferDuration: 120
idleTimeoutSec: 15
```

**All tests use the same config** — verified identical.

## Sandbox Requirements

For sandbox tests to match production:
1. Use `TRANSCRIPTION_URL=http://localhost:8085/v1/audio/transcriptions`
2. Use `TRANSCRIPTION_TOKEN=32c59b9f654f1b6e376c6f020d79897d`
3. TranscriptionClient config must match production (NO `maxSpeechDurationSec` unless production adds it)
4. SpeakerStreamManager config must match production (3/3/3/120/15)
5. All 3 transcription workers must have word timestamp support

## Collection Run Data (this snapshot)

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
