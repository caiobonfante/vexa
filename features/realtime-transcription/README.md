# Realtime Transcription

## Why

Core feature. A bot joins a meeting, captures audio, transcribes it in real-time with auto-detected language, and delivers speaker-labeled segments to clients via WebSocket and REST API.

## What

### The Shared Pipeline: SpeakerStreamManager

Both platforms (Google Meet and MS Teams) feed audio into the same core component: `SpeakerStreamManager` (`services/vexa-bot/core/src/services/speaker-streams.ts`). This is where buffering, Whisper submission, confirmation, and segment emission happen. Platform-specific code only handles how audio enters the manager and how speaker names are resolved.

**Current implementation:**

```
feedAudio(speakerId, chunk)     ← platform calls this with audio data
    |
    v
buffer accumulates chunks
    |
trySubmit() fires every 2s ────→ submitBuffer(): combine ALL chunks into WAV
    |                                  |
    |                                  v
    |                           TranscriptionClient.transcribe()
    |                           HTTP POST WAV → transcription-service (faster-whisper)
    |                                  |
    |                                  v
    |                           result: { text, language, segments[] }
    |                                  |
    v                                  v
handleTranscriptionResult()     quality gate (no_speech, logprob, hallucination filter)
    |
    v
full string match: does text exactly match previous result?
    |
    yes (3 consecutive) ──→ CONFIRMED: emit segment, advance offset
    no ──→ update lastTranscript, wait for next submission
```

### Buffer Management: Offset-Based Sliding Window

Ported from the WhisperLive service (`services/WhisperLive/whisper_live/server.py`, removed at `752e075`).

**Two offset pointers into a continuous audio stream:**

```
frames_offset                timestamp_offset
     |                            |
     v                            v
[====confirmed/trimmed============|=====unprocessed audio=====>]
                                  ^
                          next Whisper submission starts here
```

- **`frames_offset`** — oldest audio retained in memory
- **`timestamp_offset`** — start of unprocessed audio (confirmed audio is before this)

**The algorithm:**

1. Audio chunks append continuously to the buffer
2. Each Whisper submission sends `buffer[timestamp_offset:]` — only unprocessed audio
3. Whisper returns **segments** (each with `start`, `end`, `text`, `completed`)
4. **Completed segments** (all except last): emit, advance `timestamp_offset` past their end
5. **Last segment** (partial): send as live draft, do NOT advance — re-sent with more context next time
6. **Same output repeated N times**: partial IS complete — emit, advance
7. **Buffer cap**: when total audio exceeds max size, trim oldest confirmed audio from front

**Why this works:** Whisper decides segment boundaries, not our code. Whisper's segments align with natural sentence/phrase breaks. We just track which are confirmed and advance the pointer. No full reset, no scatter, no context loss.

**WhisperLive's key parameters:**
- `max_buffer_s = 45` — total audio in memory
- `discard_buffer_s = 30` — trim this much when buffer exceeds max
- `clip_if_no_segment_s = 25` — if no valid segment for 25s, force clip
- `clip_retain_s = 5` — keep last 5s when clipping
- `same_output_threshold = 3` — confirm partial after 3 identical outputs

### Downstream: How Segments Reach Clients

```
SpeakerStreamManager.onSegmentConfirmed()
  → SegmentPublisher: Redis XADD to transcription_segments stream + PUBLISH to pub/sub channel
  → transcription-collector: XREADGROUP, speaker mapping, dedup
  → Redis Hash (mutable for 30s — speaker names and text can update)
  → Background task: after 30s immutability threshold → INSERT Postgres (permanent)
  → WebSocket: live clients receive via Redis pub/sub PUBLISH
  → REST: GET /transcripts/{meeting_id} merges Redis Hash + Postgres
```

### Two Platform Audio Architectures

Both feed into the same SpeakerStreamManager, just differently:

| Platform | Audio Source | Speaker Identity | SpeakerStreamManager Instances |
|----------|------------|-----------------|-------------------------------|
| **Google Meet** | N separate `<audio>` elements, one per participant. Clean single-voice. | DOM class mutations + voting/locking (3 votes, 70% ratio) | N (one per channel) |
| **MS Teams** | 1 mixed `<audio>` element, all participants combined. | Live captions `[data-tid="author"]` | 1 (on mixed stream, caption boundaries label output) |

**Google Meet (multi-channel):**
```
Participant A ──→ ScriptProcessor A ──→ SpeakerStreamManager A ──→ Whisper ──→ segments
Participant B ──→ ScriptProcessor B ──→ SpeakerStreamManager B ──→ Whisper ──→ segments
```
N independent pipelines. No diarization needed — speakers pre-separated at recording level.

**MS Teams (single-channel):**
```
All speakers ──→ 1 mixed stream ──→ 1 SpeakerStreamManager ──→ Whisper ──→ segments with word timestamps
                                                                              |
Live captions ──→ speaker boundaries (who spoke when) ────────────────→ label words by timestamp
```
Whisper returns word-level timestamps (`timestamp_granularities=word`): each word has `{word, start, end}`. Caption says "Alice spoke 10.0s-15.2s" → match words by their timestamps → attribute to Alice. This gives word-level speaker attribution on the mixed stream.
One pipeline on mixed stream. Whisper transcribes everything. Caption speaker changes split output between speakers.

### Components

| Component | Role | Key file |
|-----------|------|----------|
| **speaker-streams** | Core buffering, submission, confirmation, emission | `services/vexa-bot/core/src/services/speaker-streams.ts` |
| **transcription-client** | HTTP POST WAV to transcription-service, requests word timestamps | `services/vexa-bot/core/src/services/transcription-client.ts` |
| **transcription-service** | faster-whisper inference, returns segments with word-level timestamps | `services/transcription-service/main.py` |
| **segment-publisher** | Redis XADD + PUBLISH | `services/vexa-bot/core/src/services/segment-publisher.ts` |
| **speaker-identity** | Track→speaker voting/locking (Google Meet only) | `services/vexa-bot/core/src/services/speaker-identity.ts` |
| **transcription-collector** | Consumes Redis stream, maps speakers, persists | `services/transcription-collector/main.py` |
| **api-gateway** | WebSocket (live) + REST (historical) | `services/api-gateway/` |
| **vexa-bot** | Orchestrates everything, platform handlers | `services/vexa-bot/core/src/index.ts` |

## How

### Implementation Status

**Step 0 (done):** Document architecture.

**Step 1 (done):** Offset-based SpeakerStreamManager.
- `confirmedSamples` pointer tracks confirmed audio, `submitBuffer` sends only unconfirmed
- Offset advances to Whisper's `segment.end` boundary (not full buffer)
- Full string match for confirmation (3 consecutive identical outputs)
- `maxSpeechDurationSec=15` — Whisper VAD forces segment splits, shorter segments
- Word-level timestamps from Whisper (`timestamp_granularities=word`)
- Tested: 92.7% content accuracy on 43s monologue, zero boundary artifacts

**Step 2 (done):** Tested on MS Teams with TTS speaker bots.
- 5 conversation runs, 18 utterances each
- Validated: monologues, speaker transitions, short utterances, multilingual (Russian)

**Step 3 (pending):** Test on Google Meet.

**Known issue:** Full string match never confirms mid-stream (Whisper output keeps changing slightly as buffer grows). Segments only emit on idle timeout or speaker change. Next step: process Whisper's segments array — emit completed segments directly, only use same-output match for the last partial segment (the WhisperLive approach).

### Current Config

| Parameter | Value | Why |
|-----------|-------|-----|
| `submitInterval` | 3s | Balance between latency and Whisper efficiency |
| `confirmThreshold` | 3 | 3 identical outputs — ensures text fully stabilized |
| `minAudioDuration` | 3s | Don't submit tiny chunks |
| `maxBufferDuration` | 120s | Trim buffer front at 2 min |
| `idleTimeoutSec` | 15s | High because browser silence filter makes pauses look idle |
| `maxSpeechDurationSec` | 15s | Whisper forces segment split — shorter segments confirm faster |

### Verify

1. `make all` from `deploy/compose/`
2. Create a live meeting, send a bot
3. Connect WS, speak, verify live segments with correct speakers
4. `GET /transcripts/{meeting_id}` — same segments
5. Test: monologue >60s, rapid multi-speaker, multilingual

### Platform-Specific Docs

- [Google Meet](google-meet/README.md) — multi-channel, per-element audio, voting/locking
- [MS Teams](ms-teams/README.md) — single-channel, mixed stream, caption-driven labeling

### Research References

- [Collabora WhisperLive](https://github.com/collabora/WhisperLive) — our codebase ancestor, sliding window server
- [UFAL whisper_streaming](https://github.com/ufal/whisper_streaming) — Local Agreement policy for streaming Whisper
- [WhisperLiveKit](https://github.com/QuentinFuxa/WhisperLiveKit) — SimulStreaming + Streaming Sortformer (SOTA 2025)
- [DiCoW](https://www.sciencedirect.com/science/article/abs/pii/S088523082500066X) — Diarization-Conditioned Whisper
- [Deepgram: Multichannel vs Diarization](https://deepgram.com/learn/multichannel-vs-diarization) — industry comparison
