# Realtime Transcription

## Why

This is the #1 product feature. Users need live, speaker-attributed transcripts during meetings -- not after. A bot joins the meeting, captures per-speaker audio, transcribes it in real-time, and delivers segments to clients as they happen. Every other feature (summaries, action items, search) depends on this pipeline producing accurate, timely, speaker-labeled segments.

## What

### Full Pipeline

```
Bot joins meeting
  -> per-speaker audio capture (platform-specific)
  -> speaker identity resolution (voting/locking for GMeet, caption name for Teams)
  -> SpeakerStreamManager buffering (offset-based, sliding window)
  -> TranscriptionClient.transcribe() (HTTP POST WAV to transcription-service)
  -> Whisper returns segments with start/end/text
  -> completed segments advance the offset, partial stays for re-transcription
  -> SegmentPublisher: Redis XADD to `transcription_segments` stream
  -> transcription-collector consumes stream
  -> speaker mapping + Redis Hash (mutable, live segments)
  -> background task: Redis Hash -> Postgres (immutable, after 30s threshold)
  -> WebSocket delivery (live, from Redis pub/sub)
  -> REST delivery (historical, from Postgres + Redis Hash merge)
```

### Platform Architecture

| Platform | Audio Model | Speaker Identity | Audio Quality |
|----------|------------|-----------------|---------------|
| **Google Meet** | Per-element audio streams. Each participant = separate `<audio>` element. Clean single-voice audio per track. | Speaking class mutations + MutationObserver + polling fallback. Voting/locking: correlate speaking indicator with audio track index. | Clean — one voice per stream, no diarization needed |
| **MS Teams** | ONE mixed audio stream. Single `<audio>` element with all participants mixed. | **Primary:** Live captions (`[data-tid="author"]`). Captions only fire on real speech. **Fallback:** DOM `voice-level-stream-outline` + `vdi-frame-occlusion`. | Mixed — all speakers combined, routed by caption timing |

### Buffer Management: The WhisperLive Algorithm

The core buffering algorithm is ported from the WhisperLive service (`services/WhisperLive/whisper_live/server.py`, removed at commit `752e075` but algorithm preserved). This is the reference implementation.

**Two offset pointers into a continuous audio stream:**

```
frames_offset                timestamp_offset
     |                            |
     v                            v
[====confirmed/discarded==========|=====unprocessed audio=====>]
                                  ^
                          next Whisper submission starts here
```

- **`frames_offset`** — start of audio buffer in memory (oldest retained audio)
- **`timestamp_offset`** — start of unprocessed audio (confirmed audio is before this)

**How it works:**

1. Audio chunks append continuously to the buffer
2. Each Whisper submission sends `buffer[timestamp_offset:]` — only unprocessed audio, NOT the full buffer
3. Whisper returns **segments** (each with start, end, text, completed flag)
4. **Completed segments**: append to transcript, advance `timestamp_offset` by segment end time
5. **Last segment** (partial): send to client as live update, do NOT advance offset — this audio will be re-sent with more context next time
6. **Same output repeated N times** (`same_output_threshold`): the partial IS complete — append to transcript, advance offset
7. Buffer hard cap (45s): when exceeded, discard oldest 30s, advance `frames_offset`

**Key insight: Whisper decides what's complete, not our code.** Whisper's segment boundaries ARE the natural sentence/phrase boundaries. We just track which segments are confirmed (appeared in 2+ consecutive results) and advance the pointer past them.

**What this means for implementation:**

| Concern | WhisperLive approach | Current SpeakerStreamManager |
|---------|---------------------|------------------------------|
| What gets sent to Whisper | `buffer[timestamp_offset:]` (unprocessed only) | Full buffer every time (re-sends confirmed audio) |
| On confirmation | Advance offset pointer, keep buffer | `emitAndReset` — clears chunks, resets transcript |
| Buffer lifetime | Continuous until speaker ends or hard cap | Reset every confirmation (~6-8s) |
| Segment boundaries | Whisper's native segments (start/end/text) | Fuzzy 80% prefix match on full transcript string |
| Sliding window | 45s max, discard 30s oldest, retain 5s | No window — full buffer or full reset |

### Data Flow

```
 BROWSER (page.evaluate)                   NODE.JS (vexa-bot)
 ======================                   ==================

 Google Meet:                              handlePerSpeakerAudioData(index, data)
   <audio> per participant                    |
     -> AudioContext(16kHz)                   +-> resolveSpeakerName (voting/locking)
     -> ScriptProcessor(4096)                 |
     -> silence check (>0.005)                v
     -> __vexaPerSpeakerAudioData(i, data)   SpeakerStreamManager.feedAudio()
                                              |
 Teams:                                    handleTeamsAudioData(name, data)
   <audio> single mixed stream                |
     -> AudioContext(16kHz)                   +-> speakerId = `teams-${name}`
     -> ScriptProcessor(4096)                 |   (name from caption, no voting)
     -> RMS silence filter (< 0.01)           v
     -> audioQueue (3s max age)            SpeakerStreamManager.feedAudio()
     -> caption observer (speaker name)       |
     -> flush on caption text growth          |
     -> 2s lookback on speaker change         |
                                              v
 handleTeamsCaptionData(name, text, ts)    trySubmit() every 2s
   -> flushSpeaker(previous) on change       submit buffer[timestamp_offset:]
   -> skip flush if < 2s audio               -> TranscriptionClient.transcribe()
                                              -> HTTP POST WAV to Whisper
                                              -> segments with start/end/text
                                              |
                                              v
                                           handleTranscriptionResult()
                                              completed segments -> advance offset, emit
                                              partial segment -> update live draft
                                              same output Nx -> confirm and advance
                                              |
                                              v
                                           SegmentPublisher -> Redis
                                              -> transcription-collector
                                              -> Redis Hash (mutable 30s)
                                              -> Postgres (immutable)
                                              -> WebSocket (live) + REST (historical)
```

### Components

| Component | Role | Key file |
|-----------|------|----------|
| **vexa-bot** | Joins meeting, captures audio, runs pipeline | `services/vexa-bot/core/src/index.ts` |
| **speaker-streams** | Per-speaker buffering with offset-based advancement | `services/vexa-bot/core/src/services/speaker-streams.ts` |
| **speaker-identity** | Track-to-speaker voting/locking (Google Meet) | `services/vexa-bot/core/src/services/speaker-identity.ts` |
| **segment-publisher** | Redis XADD + PUBLISH for segments and speaker events | `services/vexa-bot/core/src/services/segment-publisher.ts` |
| **transcription-client** | HTTP POST WAV to transcription-service | `services/vexa-bot/core/src/services/transcription-client.ts` |
| **transcription-service** | faster-whisper inference, returns segments | `services/transcription-service/main.py` |
| **transcription-collector** | Consumes Redis stream, maps speakers, persists | `services/transcription-collector/main.py` |
| **api-gateway** | WebSocket (live) + REST (historical) | `services/api-gateway/` |

### Teams-Specific: Caption-Driven Pipeline

Teams has one mixed audio stream. Speaker attribution uses live captions:

1. **Audio queue** (browser): chunks accumulate with timestamps, max age 3s, RMS silence filter drops quiet chunks
2. **Caption observer**: MutationObserver on `[data-tid="closed-caption-renderer-wrapper"]`, polls every 200ms as backup
3. **On caption text growth**: flush audio queue to the caption's speaker name via `__vexaTeamsAudioData(speaker, data)`
4. **On speaker change in captions**: flush previous speaker's SpeakerStreamManager buffer (if >= 2s audio), flush queue to new speaker with 2s lookback (discard older stale chunks)
5. **Idle timeout (15s)**: if no audio arrives for 15s, submit remaining buffer and clean up. Set high because browser silence filter makes natural speech pauses look like idle gaps.

### Key Behaviors

- **Offset-based buffer advancement:** Confirmed segments advance `timestamp_offset`. Next Whisper submission sends only unprocessed audio. Buffer stays continuous — no reset, no scatter.
- **Speaker change = buffer flush:** When captions indicate a new speaker, the previous speaker's buffer is flushed (emit + full reset). Short segments (< 2s) stay in buffer for the speaker's next turn.
- **Whisper segments, not string matching:** Whisper returns native segments with start/end times. Completed segments (all except last) get emitted. The last segment is partial — re-sent with more context on the next submission.
- **Same-output confirmation:** When the partial segment text repeats N times (same_output_threshold), it's confirmed as complete and emitted. This is the original WhisperLive algorithm.
- **Silence filter:** Browser-side RMS check (< 0.01 for Teams, > 0.005 for GMeet) prevents silent chunks from entering the pipeline. Prevents silence contamination on speaker transitions.
- **Mutable then immutable:** Segments live in Redis Hash for 30s (updates allowed), then written to Postgres (permanent).
- **Language detection:** Auto-detected per speaker. Results with probability < 0.3 discarded. Explicit language overrides. Whisper supports ~100 languages with adaptive detection.

## How

### Verify

1. Start the compose stack: `make all` (from `deploy/compose/`)
2. Create a live meeting (Google Meet or Teams) using a browser session
3. Send a bot to join the meeting
4. Connect to WS: `wscat -c ws://localhost:8056/ws -H "X-API-Key: <token>"`
5. Speak in the meeting — verify live segments arrive with correct speaker names
6. After meeting ends, verify `GET /transcripts/{meeting_id}` returns all segments
7. Compare WS delivery to REST — same segments, same speakers

Testing uses **real live meetings** created on-demand via browser sessions.

### Platform-Specific Docs

- [Google Meet flow](google-meet/README.md)
- [MS Teams flow](ms-teams/README.md)

### Documentation Pages

- [Per-Speaker Audio Architecture](../../docs/per-speaker-audio.mdx)
- [Speaker Events](../../docs/speaker-events.mdx)
- [WebSocket API](../../docs/websocket.mdx)
- [Concepts](../../docs/concepts.mdx)

### Known Limitations

- **Teams mixed audio**: overlapping speech within the caption delay window (~1-2s) cannot be separated. Fast back-to-back turns may attribute audio to the wrong speaker.
- **Teams captions assume one language**: if a speaker switches language, captions produce gibberish. Whisper auto-detects correctly but the caption routing may be disrupted.
- **Google Meet class names**: obfuscated (`Oaajhc`, `gjg47c`), may change with Meet UI updates.
- **First seconds**: new speakers may show empty until identity locks (3 votes, Google Meet) or first caption (Teams).
- **Whisper latency**: 1-3s per submission on top of the 2s submit interval.

### Implementation Status (as of 2026-03-20)

The SpeakerStreamManager currently uses full-buffer-reset on confirmation (the old approach). The WhisperLive offset-based algorithm described above is the target architecture. Key changes needed:

1. Add `timestampOffset` / `framesOffset` to SpeakerBuffer
2. `submitBuffer` sends `chunks[timestampOffset:]` not full buffer
3. Use Whisper's native segments (start/end/text/completed) instead of fuzzy string matching
4. On completed segments: advance offset, emit, keep buffer
5. On partial segment: update live draft, don't advance
6. Sliding window: trim buffer front when exceeding max size (120s)
