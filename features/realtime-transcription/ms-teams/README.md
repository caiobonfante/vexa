# MS Teams Realtime Transcription

## Why

Teams provides ONE mixed audio stream for all participants. Unlike Google Meet (which gives per-speaker streams), we can't separate speakers at the audio level. But Teams gives us something Google Meet doesn't: **live captions with perfect speaker attribution**. The architecture uses this: transcribe the mixed stream with Whisper, label segments with caption speaker boundaries.

## What

### Architecture: Audio + Captions -> Speaker-Attributed Segments

```
+------------------------- BROWSER (page.evaluate) -------------------------+
|                                                                            |
|  +----------------+     +----------------+     +------------------------+  |
|  | RTCPeerConn    |---->| <audio> elem   |---->| ScriptProcessor        |  |
|  | hook           |     | (mixed audio)  |     | (16kHz, 4096 chunks)   |  |
|  | (join.ts)      |     |                |     | RMS silence filter     |  |
|  +----------------+     +----------------+     +----------+-------------+  |
|                                                           |                |
|                                                           v                |
|  +----------------+                           +------------------------+   |
|  | Caption DOM    |                           | Audio Queue            |   |
|  | Observer       |                           | (ring buffer, 3s max)  |   |
|  | (recording.ts) |                           | chunks wait here       |   |
|  |                |                           +----------+-------------+   |
|  | Watches:       |                                      |                 |
|  | [data-tid=     |    speaker change?                   |                 |
|  |  "author"]     |------ YES --> flush queue ---------->|                 |
|  | [data-tid=     |              to NEW speaker          |                 |
|  |  "caption-     |                                      |                 |
|  |   text"]       |    text grew >3 chars?               |                 |
|  |                |------ YES --> flush queue ----------->|                 |
|  +----------------+              to current speaker      |                 |
|                                                          v                 |
|                                            __vexaTeamsAudioData()          |
|                                            (exposed function)              |
+----------------------------------+-------------------------------------+---+
                                   | (speaker, Float32Array)
                                   v
+------------------------- NODE.JS ------------------------------------------+
|                                                                            |
|  +------------------------------------------------------------------+     |
|  | SpeakerStreamManager                    (speaker-streams.ts)      |     |
|  |                                                                   |     |
|  |  Per-speaker buffer:  feedAudio() -> chunks accumulate            |     |
|  |  Submit timer:        every 2s -> submitBuffer() if enough data   |     |
|  |  Confirmation:        2 consecutive matching transcripts          |     |
|  |  Idle timeout:        15s no audio -> force flush                 |     |
|  |  Max buffer:          120s -> trim                                |     |
|  |                                                                   |     |
|  |  Callbacks:                                                       |     |
|  |    onSegmentReady ----------> (draft, send to Whisper)            |     |
|  |    onSegmentConfirmed ------> (final, publish)                    |     |
|  +-------------+------------------------------------------+----------+     |
|                |                                          |                |
|                v                                          v                |
|  +------------------------+              +------------------------------+  |
|  | TranscriptionClient    |              | SegmentPublisher             |  |
|  | (HTTP POST WAV)        |              | (segment-publisher.ts)       |  |
|  |                        |              |                              |  |
|  | Sends WAV to           |              | XADD -> transcription_       |  |
|  | Whisper service        |              |         segments stream      |  |
|  | Returns text +         |              | PUBLISH -> meeting:{id}:     |  |
|  | word timestamps        |              |            segments channel  |  |
|  +------------------------+              |                              |  |
|                                          | Drafts  (completed=false)    |  |
|                                          | Confirmed (completed=true)   |  |
|                                          +-------------+----------------+  |
+--------------------------------------------+-----------+-------------------+
                                              |
                                              v
+------------------------- DOWNSTREAM ---------------------------------------+
|                                                                            |
|  Redis stream --> transcription-collector --> Redis Hash (30s hold)        |
|                                           --> Postgres (persist)           |
|                                                                            |
|  Redis pub/sub --> api-gateway WS --> client (live segments)               |
|                                                                            |
|  api-gateway REST --> GET /transcripts/{id} (Hash + Postgres merge)        |
+----------------------------------------------------------------------------+
```

### The 7 Components

| # | Component | Where | Shared? | Role |
|---|-----------|-------|---------|------|
| 1 | **ScriptProcessor + Audio Queue** | Browser | Teams only | Captures mixed audio, filters silence (`RMS < 0.01`), holds chunks in 3s ring buffer. Google Meet uses per-element ScriptProcessors instead (no queue needed -- audio is already separated) |
| 2 | **Caption Observer** | Browser | Teams only | Watches Teams caption DOM for speaker name + text. Decides WHEN and to WHOM to flush the audio queue. Google Meet has no equivalent -- it uses DOM voting for speaker identity instead |
| 3 | **`__vexaTeamsAudioData`** | Browser->Node bridge | Teams only | Exposed function. Carries `(speakerName, audioArray)`. Google Meet uses `__vexaPerSpeakerAudioData(elementIndex, audioArray)` -- different signature because speaker name isn't known at capture time |
| 4 | **SpeakerStreamManager** | Node | Shared | `speaker-streams.ts` -- same code for both platforms. Per-speaker buffers, submit timer, confirmation, idle timeout. Teams uses 1 instance (mixed audio, time-sliced by captions). Google Meet uses N instances (one per audio element) |
| 5 | **TranscriptionClient** | Node | Shared | `transcription-client.ts` -- identical for both platforms. HTTP POST WAV to Whisper, returns text + word timestamps |
| 6 | **SegmentPublisher** | Node | Shared | `segment-publisher.ts` -- identical for both platforms. XADD to Redis stream, PUBLISH to pub/sub channel |
| 7 | **transcription-collector + api-gateway** | Downstream services | Shared | Platform-agnostic. Collector consumes stream, holds 30s for immutability, persists to Postgres. Gateway delivers via WS and REST |

### Critical Design Constraint

Audio and speaker identity travel **separate paths** with different latencies:
- **Audio** arrives in real-time via ScriptProcessor
- **Captions** arrive ~1-2s later from Teams ASR

The **audio queue** (ring buffer) bridges this gap -- chunks wait up to 3s for a caption to tell them which speaker they belong to. The caption observer is the **sole decision-maker** for flushing audio to a named speaker. Without it, audio accumulates in the queue and silently drops after 3s. The DOM "blue squares" speaker detection (`voice-level-stream-outline`) only records speaker events for persistence -- it does NOT route audio.

**Key insight**: we do NOT route audio to per-speaker buffers at capture time. That approach (the old architecture) caused cross-speaker contamination, silence dumps, and scattered fragments. Instead, audio queues in a ring buffer, captions decide attribution, and Whisper transcribes per-speaker chunks after routing.

### How Captions Drive Speaker Boundaries

Teams live captions are enabled by the bot after joining (More → Captions). The DOM provides:

```
[data-tid="closed-caption-renderer-wrapper"]     <- container
  └─ [data-tid="author"]                         <- speaker name
  └─ [data-tid="closed-caption-text"]            <- spoken text
```

These are the ONLY stable selectors — Teams renders different container structures for host vs guest views, but `author` and `closed-caption-text` are always present.

**Active speaker model:**

Every caption event is an `(author, text, timestamp)` triple. The **active speaker** is the last author seen. Speaker boundaries are defined by author switches:

- **Segment START** = first caption with a different author than the current active speaker
- **Segment END** = when the next author switch occurs
- **Active speaker text updates** = confirms still talking, tracked for reconciliation
- **Non-active speaker refinements** = discarded (Teams reformats punctuation on old entries)

The `speaker-mapper` module (`speaker-mapper.ts`) takes Whisper's word timestamps and maps each word to the speaker boundary with most time overlap. Words that straddle a boundary go to the speaker with more overlap time. Words in gaps go to the nearest speaker.

**Caption delay impact:** Captions arrive 1-2s after speech (variable). This shifts speaker boundaries forward — the first few words of a new speaker may fall within the previous speaker's delayed boundary. Tested: at mean 1.5s delay, ~2 words per speaker transition get misattributed (80% overall attribution accuracy on 3-speaker test).

**On caption speaker change:**
1. `handleTeamsCaptionData()` detects speaker changed
2. Calls `flushSpeaker(previousSpeakerId)` — emits the previous speaker's buffer as a segment
3. New audio routes to the new speaker's buffer
4. Short segments (< 2s audio) stay in buffer for the speaker's next turn

**On same speaker caption update:**
Audio continues accumulating in the same speaker's buffer. Caption text stored for reconciliation.

### Buffer Management

Uses the offset-based sliding window algorithm (see [parent README](../README.md)):

- `submitBuffer` sends only unprocessed audio (`buffer[timestampOffset:]`)
- Completed Whisper segments advance the offset
- Partial segments re-sent with more context on next submission
- Speaker change flushes the current buffer
- Idle timeout (15s) cleans up when no audio arrives
- Hard cap at 120s

### Caption Enablement

Differs by role:
- **Guest (bot):** More → Captions (direct toggle)
- **Host:** More → Language and speech → Show live captions

The bot handles both paths in `captions.ts`.

### Audio Capture

The RTCPeerConnection hook in `join.ts` intercepts remote audio tracks and mirrors them into hidden `<audio>` elements. `BrowserAudioService` combines these into one stream. A single `ScriptProcessor` processes the mixed audio at 16kHz.

Browser-side silence filter (`RMS < 0.01`) drops quiet chunks before they enter the pipeline. This prevents silence contamination on speaker transitions but means natural speech pauses (2-5s) don't reach the Node-side buffer — which is why idle timeout is set to 15s (not 5s).

### Quality Gate

Short noisy audio causes Whisper hallucinations. The bot checks per-segment signals:
- `no_speech_prob > 0.5 && avg_logprob < -0.7` → noise
- `avg_logprob < -0.8 && duration < 2s` → garbage
- `compression_ratio > 2.4` → repetitive hallucination
- `language_probability < 0.3` → wrong language

### Differences from Google Meet

| Aspect | Google Meet | MS Teams |
|--------|-----------|----------|
| Audio | N per-speaker streams | 1 mixed stream |
| SpeakerStreamManager instances | N (one per channel) | 1 (on mixed stream) |
| Speaker identity | DOM voting/locking | Caption author |
| Diarization | Not needed (pre-separated) | Caption boundaries label output |
| Overlapping speech | Natural (separate streams) | Both speakers in same audio |
| Language | Whisper auto-detects per stream | Whisper auto-detects (captions may be wrong language) |

### Known Limitations

1. **Overlapping speech** — single mixed stream. Both speakers' words appear in the same Whisper output; the caption-active speaker gets attribution.
2. **Caption delay ~1-2s** — speaker transitions within this window may misattribute a few words.
3. **Captions assume one language** — if a speaker switches language, Teams captions produce gibberish. Whisper detects the correct language but the caption text can't be used for reconciliation.
4. **Short interjections** — single words ("Agreed.", "OK.") from a different speaker may be absorbed into the adjacent speaker's segment if the caption change is too brief.

### Reference: Teams Caption Behavior

See [teams-caption-behavior.md](teams-caption-behavior.md) for detailed observations from real meetings:
- Text growth patterns (word-by-word, ~400ms cadence)
- Sentence splitting (text shrinks when Teams reformats)
- Overlap behavior (first speaker truncated mid-word)
- Caption delay distribution
- Numbers and formatting rules
- Constants for test simulation

Reference data: caption event observations documented in the behavior file above (original `tests/reference-caption-data.json` has been removed).

## How

### File Map

| File | Purpose |
|------|---------|
| `recording.ts` | Browser-side: audio queue, silence filter, caption observer, audio routing |
| `captions.ts` | Enable live captions (guest + host paths) |
| `selectors.ts` | DOM selectors. Captions: `[data-tid="author"]` + `[data-tid="closed-caption-text"]` |
| `join.ts` | RTCPeerConnection hook for audio capture, pre-join flow |
| `index.ts` (shared) | `handleTeamsAudioData()`, `handleTeamsCaptionData()`, quality gate |

### Testing

Real live Teams meetings with TTS-speaking bots (Alice, Bob using different user accounts). Test conversation script drives multi-speaker dialogue with normal turns, back-to-back, overlap, and short interjections. Results validated against ground truth input text.

**Current results (2026-03-23):**

| Test | Segments found | Speaker accuracy | WER |
|------|---------------|-----------------|-----|
| E2E (`tests/e2e/test-e2e.sh`) | 9/9 (100%) | 100% | 14% |
| Stress (`tests/e2e/test-e2e-stress.sh`) | 18/20 (90%) | 100% | 15% |

Teams meetings require a `passcode` field in the bot creation API. Without it, anonymous bots cannot pass the lobby. The API rejects unknown fields (extra fields forbidden).
