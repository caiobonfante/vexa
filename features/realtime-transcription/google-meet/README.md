# Google Meet Realtime Transcription

## Why

Google Meet provides the cleanest audio pipeline of any supported platform. Each participant gets a separate `<audio>` element with its own MediaStream — true **multi-channel audio**. No diarization needed, no mixed audio, no cross-talk. This is the equivalent of multichannel transcription, the industry gold standard for accuracy.

## What

### Architecture: Per-Speaker Streams -> Voting -> Transcription

```
+------------------------- BROWSER (page.evaluate) -------------------------+
|                                                                            |
|  Google Meet provides N separate <audio> elements (one per participant).   |
|  Each gets its own AudioContext + ScriptProcessor.                         |
|                                                                            |
|  +----------------+  +----------------+  +----------------+               |
|  | <audio> A      |  | <audio> B      |  | <audio> C      |  ... N       |
|  | (participant)  |  | (participant)  |  | (participant)  |               |
|  +-------+--------+  +-------+--------+  +-------+--------+               |
|          |                    |                    |                        |
|          v                    v                    v                        |
|  +----------------+  +----------------+  +----------------+               |
|  | AudioContext A  |  | AudioContext B  |  | AudioContext C  |               |
|  | ScriptProc A   |  | ScriptProc B   |  | ScriptProc C   |               |
|  | 16kHz, 4096    |  | 16kHz, 4096    |  | 16kHz, 4096    |               |
|  | silence >0.005 |  | silence >0.005 |  | silence >0.005 |               |
|  +-------+--------+  +-------+--------+  +-------+--------+               |
|          |                    |                    |                        |
|          +--------------------+--------------------+                       |
|                               |                                            |
|                               v                                            |
|                __vexaPerSpeakerAudioData(index, data)                      |
|                (exposed function, per-element index)                       |
|                                                                            |
|  IN PARALLEL:                                                              |
|  +--------------------------------------------------------------+         |
|  | Speaker Detection (recording.ts)                              |         |
|  |                                                               |         |
|  | MutationObserver on [data-participant-id] tiles               |         |
|  | Watches speaking classes: Oaajhc, HX2H7, wEsLMd, OgVli       |         |
|  | + 500ms polling fallback                                      |         |
|  |                                                               |         |
|  | Exposes: __vexaGetAllParticipantNames()                       |         |
|  |   -> { names: {id: name}, speaking: [name] }                 |         |
|  +--------------------------------------------------------------+         |
+----------------------------------+-------------------------------------+---+
                                   | (elementIndex, Float32Array)
                                   v
+------------------------- NODE.JS ------------------------------------------+
|                                                                            |
|  handlePerSpeakerAudioData(speakerIndex, audioData)                        |
|       |                                                                    |
|       v                                                                    |
|  +--------------------------------------------------------------+         |
|  | Speaker Identity Voting           (speaker-identity.ts)       |         |
|  |                                                               |         |
|  |  On each audio chunk:                                         |         |
|  |    Query browser: who is speaking? (DOM indicators)           |         |
|  |    If exactly 1 speaker active: vote(trackN = speakerName)    |         |
|  |    After 3 votes at 70% ratio: LOCK permanently               |         |
|  |    Locked tracks return instantly, no more queries             |         |
|  |    Constraint: one-name-per-track, one-track-per-name          |         |
|  |                                                               |         |
|  |  Re-resolve every 2s if unmapped, 5s if named but unlocked    |         |
|  +--------------------------------------------------------------+         |
|       |                                                                    |
|       v                                                                    |
|  +------------------------------------------------------------------+     |
|  | SpeakerStreamManager (N instances)        (speaker-streams.ts)    |     |
|  |                                                                   |     |
|  |  One buffer per speaker-{index}:                                  |     |
|  |    feedAudio() -> chunks accumulate                               |     |
|  |    Submit timer: every 2s -> submitBuffer() if enough data        |     |
|  |    Confirmation: 2 consecutive matching transcripts               |     |
|  |    Idle timeout: 15s no audio -> force flush                      |     |
|  |    Max buffer: 120s -> trim                                       |     |
|  |    VAD (Silero): disabled — chunks too short for reliable detect  |     |
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
|  | Returns text +         |              | PUBLISH -> tc:meeting:{id}:  |  |
|  | word timestamps        |              |            mutable channel   |  |
|  +------------------------+              |                              |  |
|                                          | Bundle per tick: confirmed   |  |
|                                          | + pending draft per speaker  |  |
|                                          +-------------+----------------+  |
+--------------------------------------------+-----------+-------------------+
                                              |
                                              v
+------------------------- DOWNSTREAM ---------------------------------------+
|                                                                            |
|  Redis stream --> transcription-collector --> Redis Hash (30s hold)        |
|                                           --> Postgres (persist)           |
|                                                                            |
|  Bot PUBLISH tc:meeting:{id}:mutable --> api-gateway WS --> client (live)  |
|                                                                            |
|  api-gateway REST --> GET /transcripts/{id} (Hash + Postgres merge)        |
+----------------------------------------------------------------------------+
```

### The 8 Components

| # | Component | Where | Shared? | Role |
|---|-----------|-------|---------|------|
| 1 | **Per-Element ScriptProcessors** | Browser | Google Meet only | N independent AudioContexts at 16kHz, one per `<audio>` element. Silence filter (`maxVal > 0.005`) per stream. Teams uses a single ScriptProcessor + ring buffer instead (mixed audio) |
| 2 | **Speaker Detection** | Browser | Google Meet only | MutationObserver on participant tiles + 500ms polling. Detects who is speaking via CSS class changes. Teams uses live captions for speaker identity instead |
| 3 | **`__vexaPerSpeakerAudioData`** | Browser->Node bridge | Google Meet only | Exposed function. Carries `(elementIndex, audioArray)` -- index identifies which stream. Teams uses `__vexaTeamsAudioData(speakerName, audioArray)` -- different signature because speaker name is known from captions |
| 4 | **Speaker Identity Voting** | Node | Google Meet only | `speaker-identity.ts` -- correlates "which track has audio" with "which DOM tile is speaking." 3 votes at 70% -> permanent lock. Teams doesn't need this -- captions provide speaker names directly |
| 5 | **SpeakerStreamManager (N instances)** | Node | Shared | `speaker-streams.ts` -- same code for both platforms. Google Meet uses N instances (one per audio element). Teams uses 1 instance (mixed audio, time-sliced by captions) |
| 6 | **TranscriptionClient** | Node | Shared | `transcription-client.ts` -- identical for both platforms. HTTP POST WAV to Whisper, returns text + word timestamps |
| 7 | **SegmentPublisher** | Node | Shared | `segment-publisher.ts` -- identical for both platforms. XADD to Redis stream, PUBLISH to pub/sub channel |
| 8 | **transcription-collector + api-gateway** | Downstream services | Shared | Platform-agnostic. Collector consumes stream, holds 30s for immutability, persists to Postgres. Gateway delivers via WS and REST |

### Critical Design Constraint

Google Meet gives **clean per-speaker audio** (no mixed stream, no diarization needed) but **doesn't tell you who each stream belongs to**. The voting system bridges this gap:

- Audio activity and DOM speaking indicators are **correlated over time**
- Voting only works when **exactly 1 speaker** is active (can't disambiguate during overlap)
- Once locked (3 votes, 70% ratio), mapping is **permanent** for the session
- Before locking, early audio may be attributed to `""` (unmapped) -- segments still captured, speaker name may update retroactively

Unlike Teams (which relies on a single caption activation button), Google Meet's per-speaker architecture has **no single choke point** for audio capture. Each stream is independent -- if one fails, others continue.

### Audio Capture

**File:** `services/vexa-bot/core/src/index.ts` (`startPerSpeakerAudioCapture`)

1. `page.evaluate()` discovers active media elements: `<audio>` and `<video>` filtered by `!el.paused && srcObject.getAudioTracks().length > 0`
2. Retries up to 10 times (20s total)
3. Per element: `new AudioContext({ sampleRate: 16000 })` → `createScriptProcessor(4096, 1, 1)`
4. Silence filter: `maxVal > 0.005` before sending
5. References stored on `window.__vexaAudioStreams` to prevent GC

### Speaker Identity: Voting/Locking

**The problem:** Google Meet doesn't expose which audio element belongs to which participant.

**The solution:** Correlate "which track has audio" with "which DOM tile shows speaking."

**Files:**
- `speaker-identity.ts` — voting/locking logic
- `googlemeet/recording.ts` — browser-side speaking detection

**Flow:**
1. Audio arrives on track N → `handlePerSpeakerAudioData(N, data)`
2. Query browser: `__vexaGetAllParticipantNames()` → `{ names: {id: name}, speaking: [name] }`
3. If exactly 1 speaker active: `recordTrackVote(N, speakerName)`
4. After `LOCK_THRESHOLD=3` votes with `LOCK_RATIO=0.7`: mapping locks permanently
5. Constraints: one-name-per-track, one-track-per-name

**Speaking detection (browser-side):**
- MutationObserver on class changes within `[data-participant-id]` containers
- Watches for speaking classes: `Oaajhc`, `HX2H7`, `wEsLMd`, `OgVli`
- Silence class: `gjg47c`
- 500ms polling fallback for cases where mutations don't fire

**Practical behavior:** In TTS bot tests, the voting/locking mechanism rarely fires (0 `LOCKED PERMANENTLY` events observed). The real protection against misattribution is the `isDuplicateSpeakerName` dedup check in `index.ts`, which rejects any speaker name already assigned to another track. This means identity resolution works primarily through first-assignment dedup rather than vote accumulation. The voting system remains as designed backup for ambiguous cases with human participants.

### Buffer Management

Uses the same offset-based sliding window as Teams (see [parent README](../README.md)):

- Each speaker gets independent `SpeakerStreamManager` instance
- `submitBuffer` sends only unprocessed audio
- Completed Whisper segments advance the offset
- VAD (Silero) loaded but **disabled** — 4096-sample chunks (256ms) are too short for reliable detection; Whisper's own `no_speech_prob` handles silence rejection downstream
- Speaker leaving/muting triggers idle timeout → clean buffer flush

### GC Prevention

**Critical:** Web Audio API `ScriptProcessor` nodes are garbage collected if no JavaScript reference holds them. All references stored on `window.__vexaAudioStreams`:

```typescript
(window as any).__vexaAudioStreams.push({ ctx, source, processor });
```

Without this, audio capture silently stops within seconds.

### Differences from MS Teams

| Aspect | Google Meet | MS Teams |
|--------|-----------|----------|
| Audio | N per-speaker streams | 1 mixed stream |
| SpeakerStreamManager | N instances (one per channel) | 1 instance (mixed) |
| Speaker identity | DOM voting/locking + dedup (inferred) | Caption author (explicit) |
| Diarization | Not needed | Caption boundaries |
| Overlapping speech | Natural separation | Both in same stream |
| VAD | Silero loaded but disabled (chunks too short) | Browser-side RMS filter |
| Silence filter | `maxVal > 0.005` per element | `RMS < 0.01` on mixed stream |

### Key Selectors

| Selector | Purpose |
|----------|---------|
| `[data-participant-id]` | Participant tile |
| `span.notranslate` | Participant name |
| `.Oaajhc` | Speaking animation class |
| `.gjg47c` | Silence class |
| `button[aria-label="Leave call"]` | Leave button |
| `[jsname="BOHaEe"]` | Meeting container |

These are obfuscated Google Meet class names. They change with UI updates — `selectors.ts` must be updated.

### How to Test (fully autonomous)

1. Ensure compose stack is running
2. Create a browser session: `POST /sessions` to bot-manager
3. Host a Google Meet:
   ```bash
   CDP_URL=<cdp_url> node features/realtime-transcription/scripts/gmeet-host-auto.js
   ```
   Outputs `MEETING_URL` and `NATIVE_MEETING_ID`.
4. Start auto-admit:
   ```bash
   CDP_URL=<cdp_url> node features/realtime-transcription/scripts/auto-admit.js <meeting_url>
   ```
5. Send bot to join: `POST /bots` with the meeting URL
6. Send TTS bots to speak (for automated testing)
7. Verify in bot logs, Redis, and REST API

No human needed — meeting creation, hosting, and lobby admission are all automated.

### Known Limitations

1. **Obfuscated class names** — Google Meet uses compiled class names that change with deployments
2. **First seconds** — speaker identity requires 3 votes to lock; first audio may be unnamed
3. **Domain-restricted meetings** — bot joins as unauthenticated guest, may be rejected by org policy
4. **Multiple speakers simultaneously** — voting only works when exactly 1 speaker is active; during overlap, no votes cast, existing locks used
5. **Speaker identity with human participants** — TTS bots produce clean single-speaker windows, but human conversations have more overlap and ambiguity. See [CAPTION-SPEAKER-DESIGN.md](CAPTION-SPEAKER-DESIGN.md) for an open design exploring caption-based speaker identity as an alternative

## How

### File Map

| File | Purpose |
|------|---------|
| `index.ts` (`startPerSpeakerAudioCapture`) | Browser-side AudioContext/ScriptProcessor per element |
| `index.ts` (`handlePerSpeakerAudioData`) | Node-side: speaker resolution, VAD, buffer feed |
| `speaker-identity.ts` | Track→speaker voting/locking, browser state queries |
| `speaker-streams.ts` | SpeakerStreamManager — offset-based sliding window (shared) |
| `googlemeet/recording.ts` | Browser-side speaker detection, MutationObserver, participant counting |
| `googlemeet/selectors.ts` | All Google Meet DOM selectors |

### Testing

Real live Google Meet meetings. No mocks — real platform behavior, real audio, real speaker detection. Test with 2+ participants speaking and verify speaker attribution locks correctly within first few seconds.

#### Test suites

- **[`tests/speaker-voting/`](tests/speaker-voting/)** — Speaker identity unit/integration tests. 9 scenarios, 41 segments, 0 misattributed, 100% speaker accuracy.
- **[`tests/e2e/`](tests/e2e/)** — End-to-end pipeline validation: TTS bots speak into live Google Meet, audio flows through Whisper, segments persist to Postgres. Stress test: 18/20 segments found, 100% speaker accuracy, 15% WER.
