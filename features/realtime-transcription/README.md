# Realtime Transcription

## Why

This is the #1 product feature. Users need live, speaker-attributed, multilingual transcripts during meetings — not after. A bot joins the meeting, captures audio, transcribes it in real-time with auto-detected language, and delivers speaker-labeled segments to clients as they happen.

## What

### Two Fundamentally Different Audio Architectures

| Platform | Audio | Speaker ID | Approach |
|----------|-------|-----------|----------|
| **Google Meet** | **Multi-channel**: N separate `<audio>` elements, one per participant. Clean single-voice streams. | DOM class mutations + voting/locking | N independent SpeakerStreamManagers, one per channel. No diarization needed. |
| **MS Teams** | **Single-channel**: ONE mixed `<audio>` element, all participants combined. | Live captions (`[data-tid="author"]`) | 1 SpeakerStreamManager on mixed stream. Caption boundaries label Whisper output with speaker names. |

### Target Architecture: Offset-Based Sliding Window

Ported from the WhisperLive service (removed at `752e075`, algorithm preserved). This is how audio buffering should work for both platforms.

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
7. **Buffer cap**: when total audio exceeds max size, trim oldest confirmed audio

**Why this works:** Whisper decides segment boundaries, not our code. Whisper's segments align with natural sentence/phrase breaks. We just track which are confirmed and advance the pointer.

### Multi-Channel (Google Meet)

```
Participant A ──→ ScriptProcessor A ──→ SpeakerStreamManager A ──→ Whisper ──→ segments
Participant B ──→ ScriptProcessor B ──→ SpeakerStreamManager B ──→ Whisper ──→ segments
Participant C ──→ ScriptProcessor C ──→ SpeakerStreamManager C ──→ Whisper ──→ segments
```

N independent pipelines. Each gets clean single-voice audio. Speaker identity from DOM voting/locking. This is the equivalent of **multichannel transcription** — the industry gold standard for accuracy because speakers are pre-separated at the recording level.

### Single-Channel (MS Teams)

```
All speakers ──→ 1 mixed stream ──→ 1 SpeakerStreamManager ──→ Whisper ──→ segments
                                                                              |
Live captions ──→ speaker boundaries (who spoke when) ──────────────────→ label segments
```

One pipeline on the mixed stream. Whisper transcribes everything. Caption speaker changes define where to split between speakers. This is **diarization-conditioned transcription** — same approach as DiCoW (2025 research), but using Teams captions as the diarization signal instead of a ML model.

**Key insight**: we don't route audio to per-speaker buffers (that's the source of all cross-speaker contamination bugs). We transcribe the mixed stream as-is and label after.

### Downstream Pipeline

```
SpeakerStreamManager
  → SegmentPublisher: Redis XADD to transcription_segments + PUBLISH
  → transcription-collector: consumes stream, maps speakers
  → Redis Hash (mutable, 30s window) → Postgres (immutable)
  → WebSocket (live, Redis pub/sub) + REST (historical, Postgres + Redis merge)
```

### Components

| Component | Role | Key file |
|-----------|------|----------|
| **vexa-bot** | Joins meeting, captures audio, runs pipeline | `services/vexa-bot/core/src/index.ts` |
| **speaker-streams** | Offset-based buffering with sliding window | `services/vexa-bot/core/src/services/speaker-streams.ts` |
| **speaker-identity** | Track-to-speaker voting/locking (Google Meet) | `services/vexa-bot/core/src/services/speaker-identity.ts` |
| **transcription-client** | HTTP POST WAV to transcription-service | `services/vexa-bot/core/src/services/transcription-client.ts` |
| **transcription-service** | faster-whisper inference, returns segments with start/end/text | `services/transcription-service/main.py` |
| **segment-publisher** | Redis XADD + PUBLISH | `services/vexa-bot/core/src/services/segment-publisher.ts` |
| **transcription-collector** | Consumes Redis, maps speakers, persists | `services/transcription-collector/main.py` |
| **api-gateway** | WebSocket (live) + REST (historical) | `services/api-gateway/` |

## How

### Implementation Plan

**Step 0 (current):** Document the architecture. This README.

**Step 1 — Baseline: offset-based SpeakerStreamManager.**
Port the WhisperLive algorithm into `speaker-streams.ts`:
- Add `timestampOffset`, `framesOffset` to SpeakerBuffer
- `submitBuffer` sends `chunks[timestampOffset:]`, not the full buffer
- Use Whisper's native segment boundaries (start/end/text/completed) from transcription-service response
- On completed segments: advance offset, emit, keep buffer
- On partial: update live draft, don't advance
- Sliding window: trim buffer when exceeding max (120s)

This change is platform-agnostic — both GMeet and Teams use the same SpeakerStreamManager.

**Step 2 — Test on MS Teams.**
Teams is the harder case (mixed audio). Validate:
- Long monologues produce continuous, non-scattered output
- Speaker transitions are clean (caption-driven labeling)
- Short utterances survive (kept in buffer for next turn)
- Multilingual detection works

**Step 3 — Test on Google Meet.**
GMeet is the easier case (per-channel audio). Validate:
- Per-channel pipelines work independently
- Speaker identity voting/locking still functions
- No regression from baseline change

### Verify

1. `make all` from `deploy/compose/`
2. Create a live meeting on the target platform
3. Send a bot, connect to WS, speak, verify live segments with correct speakers
4. After meeting, verify `GET /transcripts/{meeting_id}` matches
5. Test: single speaker monologue (>60s), rapid multi-speaker exchange, multilingual

### Platform-Specific Docs

- [Google Meet](google-meet/README.md) — multi-channel, per-element audio, voting/locking
- [MS Teams](ms-teams/README.md) — single-channel, mixed stream, caption-driven labeling

### Research References

- [UFAL whisper_streaming](https://github.com/ufal/whisper_streaming) — Local Agreement policy for streaming Whisper
- [WhisperLiveKit](https://github.com/QuentinFuxa/WhisperLiveKit) — SimulStreaming + Streaming Sortformer (SOTA 2025)
- [DiCoW](https://www.sciencedirect.com/science/article/abs/pii/S088523082500066X) — Diarization-Conditioned Whisper for multi-talker
- [WhisperX](https://github.com/m-bain/whisperX) — Word-level timestamps + diarization
- [Deepgram: Multichannel vs Diarization](https://deepgram.com/learn/multichannel-vs-diarization) — Industry comparison
- [Collabora WhisperLive](https://github.com/collabora/WhisperLive) — Original sliding window implementation (our codebase ancestor)

### Known Limitations

- **Teams overlapping speech**: within the caption delay window (~1-2s), simultaneous speakers can't be separated. The mixed audio gets one label.
- **Teams captions assume one language**: if speaker switches language, captions produce gibberish. Whisper detects correctly but caption text is unreliable.
- **Google Meet class names**: obfuscated, may change with UI updates.
- **Whisper latency**: 1-3s per submission on top of submit interval.
