# Realtime Transcription

> **Confidence: 90** — Both platforms validated. GMeet: 3 TTS + 1 human, 100% speaker accuracy, WER 18%, confirm latency 6-7s (dkn-pwrq-obk + meeting 21, 2026-03-27). Teams: E2E tests 9/9 basic + 18/20 stress, 100% speaker accuracy, 14-15% WER (2026-03-23), bot code unchanged, shared pipeline verified.
> **Tested:** Bot joins (both platforms), audio capture (per-speaker GMeet + mixed+caption Teams), Whisper transcription, VAD, segment persistence, speaker identity (GMeet: 3 TTS + 1 human, voting/locking; Teams: caption-driven routing, 100% attribution), multi-track dedup, REST API, WS delivery, confirmation logic.
> **Not tested:** 3+ distinct human speakers, 5+ speaker SFU remapping, WS live delivery during active speech, Zoom, language locking in live meeting, Teams overlapping speech attribution.
> **Contributions welcome:** Zoom implementation, faster human speaker locking, Whisper alternatives ([#148](https://github.com/Vexa-ai/vexa/issues/148), [#156](https://github.com/Vexa-ai/vexa/issues/156)).
>
> **Sub-features:** [google-meet](google-meet/) | [ms-teams](ms-teams/) | [zoom](zoom/) | [delivery](delivery/) — each with own gate, findings, tests

## Why

Core feature. A bot joins a meeting, captures audio, transcribes it in real-time with auto-detected language, and delivers speaker-labeled segments to clients via WebSocket and REST API. Self-hosted alternative to Otter.ai ($17/seat), Fireflies ($19/seat), Read.ai ($20/seat) — at infrastructure cost, data stays on your network.

This feature follows the [validation cycle](../README.md#validation-cycle) — see [glossary](../README.md#glossary) for terms.

## What

### The Shared Pipeline: SpeakerStreamManager

Both platforms (Google Meet and MS Teams) feed audio into the same core component: `SpeakerStreamManager` (`services/vexa-bot/core/src/services/speaker-streams.ts`). This is where buffering, Whisper submission, confirmation, and segment emission happen. Platform-specific code only handles how audio enters the manager and how speaker names are resolved.

**Current implementation:**

```
feedAudio(speakerId, chunk)     ← platform calls this with audio data
    |
    v
buffer accumulates chunks (min 3s before first submit)
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
per-segment stability check (primary):
    Whisper returns segments[]. For each segment position, track text stability.
    When leading segments match confirmThreshold (2) consecutive times:
    ──→ CONFIRMED: emit those segments, advance offset past their end
    |
    v (fallback, if no per-segment confirmation)
full string match:
    does entire text exactly match previous result?
    yes (2 consecutive) ──→ CONFIRMED: emit all, advance offset
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

**The algorithm (per-segment stability + full-text fallback):**

1. Audio chunks append continuously to the buffer
2. Each Whisper submission sends `buffer[timestamp_offset:]` — only unprocessed audio
3. Whisper returns **segments[]** (each with `start`, `end`, `text`)
4. **Per-segment stability** (primary path): track text at each segment position across submissions. When leading segments match `confirmThreshold` (2) consecutive times → emit confirmed, advance `timestamp_offset` past their end
5. **Full-text fallback**: if no per-segment confirmation, check if entire output text matches previous result `confirmThreshold` times → emit all, advance
6. **Idle timeout**: 15s no audio → force flush remaining buffer as confirmed
7. **Buffer cap**: when total audio exceeds max size (120s), trim oldest confirmed audio from front

**Why this works:** Whisper decides segment boundaries, not our code. Per-segment stability tracking lets leading segments confirm and emit while the last segment is still evolving — no need to wait for the entire buffer to stabilize.

**WhisperLive's key parameters:**
- `max_buffer_s = 45` — total audio in memory
- `discard_buffer_s = 30` — trim this much when buffer exceeds max
- `clip_if_no_segment_s = 25` — if no valid segment for 25s, force clip
- `clip_retain_s = 5` — keep last 5s when clipping
- `same_output_threshold = 3` — confirm partial after 3 identical outputs (our implementation uses 2)

### Downstream: How Segments Reach Clients

**Current (see [delivery/README.md](delivery/README.md)):**
```
SpeakerStreamManager emits confirmed segment (segment_id, speaker, text, absolute_start_time)
  → SegmentPublisher:
      XADD transcription_segments {payload: JSON}     → collector persists
      PUBLISH tc:meeting:{id}:mutable {JSON bundle}   → api-gateway → WS → dashboard
  → transcription-collector (persistence only):
      XREADGROUP → HSET meeting:{id}:segments → background UPSERT Postgres
  → REST: merge Postgres + Redis Hash by segment_id → return all
  → Dashboard: two-map model (_confirmed by segment_id + _pendingBySpeaker)
```

Bot is the single publisher for both live delivery (WS) and persistence (stream).
Collector is persistence-only — no WS publish, no speaker mapping, no dedup.
Each WS tick sends a bundle: confirmed segments (completed=true) + pending draft for the active speaker (completed=false). Dashboard uses two-map model: confirmed by segment_id (append-only) + pendingBySpeaker (replaced per tick).

### Data Stages and Iteration Cost

This feature's data lives in `data/` organized by pipeline stage (see [features/README.md](../README.md#data--feature-data-organized-by-pipeline-stage)):

| Stage | Contents | Produced by | Consumed by |
|-------|----------|-------------|-------------|
| **raw** | audio WAVs + caption events + speaker changes + ground truth | collection run (live meeting) | transcription pipeline (middle loop) |
| **core** | confirmed segments (speaker, text, timestamps) | SpeakerStreamManager | delivery pipeline (right side), scoring |
| **rendered** | REST responses, WS captures, DB snapshots | transcription-collector + api-gateway | dashboard, clients |

```
data/
  raw/
    synthetic/            # Generated test audio (not from live meetings)
    teams-3sp-collection/ # 3 speakers, 17 utterances, diverse scenarios
    teams-7sp-panel/      # 7 speakers, 20 segments, panel discussion
    teams-5sp-stress/     # 5 speakers, stress test
    teams-meeting-328/    # Live meeting 328 capture
    ...
  core/
    teams-7sp-panel/      # Pipeline output for panel dataset
    teams-3sp-collection/ # Pipeline output for collection dataset
  rendered/
    teams-7sp-panel/      # REST/DB output for panel dataset
```

The pipeline is a chain of data stages. Each stage transforms data and has a different iteration cost:

```
[Ground Truth]   known script (TTS bots speak exact text)
      |
      v
   meeting       live platform meeting — real audio, real WebRTC, real DOM
      |
      v
    [raw]        captured audio + speaker events (per-utterance WAVs, DOM/caption events)
      |
      v
  transcription  Whisper + quality gates + hallucination filter
      |
      v
    [core]       confirmed segments from SpeakerStreamManager (speaker, text, timestamps)
      |
      v
    dedup        transcription-collector: dedup, speaker mapping, immutability threshold
      |
      v
  [rendered]     Redis Hash -> Postgres -> REST API / WebSocket
```

Three iteration loops, from cheapest to most expensive:

| Loop | Input | Process | What you're validating | Cost |
|------|-------|---------|----------------------|------|
| **Rendering** (right side) | [core] segments | collector -> dedup -> REST | Dedup logic, WS/REST delivery, speaker name mapping | Seconds, no GPU |
| **Transcription** (middle) | [raw] audio | Whisper -> SpeakerStreamManager -> [core] | Transcription accuracy, speaker attribution, buffer management, confirmation | **Real-time** (see below), needs GPU |
| **Collection** (left side) | [Ground Truth] script | Live meeting -> capture everything | End-to-end: does the real platform produce the expected raw data? | Minutes, real infra |

**The middle loop runs at real-time speed, not fast-forward.** Audio is fed through the pipeline at the same rate it was captured — a 90s meeting takes 90s to replay. This is intentional: the pipeline's behavior depends on timing (submit intervals, idle timeouts, confirmation windows, caption delays). Fast-forwarding would remove timing-dependent bugs from the test, which are exactly the bugs we need to catch.

**This means dataset design matters.** Two strategies:

- **Targeted datasets** (10-30s): Cover one specific case (speaker transition, short phrase, overlap). Fast to iterate — code change -> replay -> score in under a minute. Use these for diagnosing and fixing specific issues.
- **Validation datasets** (60-120s): Larger, unstructured, closer to real meetings. Slow to iterate but catch regressions and interactions between scenarios. Use these to confirm a fix doesn't break other cases.

When a validation dataset reveals an issue, **extract the specific segment** into a targeted dataset rather than iterating on the full meeting. Fix against the small dataset, then re-run the large one to confirm.

**Collection (live meeting) is inevitable** for two reasons:
1. Fresh raw data when you need new scenarios or a platform changes behavior
2. Human validation that metrics match subjective quality — 90% word accuracy might read terribly if the 10% errors are all speaker names, or read fine if the 10% is filler words. Only a live transcript tells you.

### Two Platform Audio Architectures

Both feed into the same SpeakerStreamManager, just differently:

| Platform | Audio Source | Speaker Identity | SpeakerStreamManager Instances |
|----------|------------|-----------------|-------------------------------|
| **Google Meet** | N separate `<audio>` elements, one per participant. Clean single-voice. | DOM class mutations + voting/locking (2 votes, 70% ratio) | N (one per channel) |
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
Whisper returns word-level timestamps (`timestamp_granularities=word`): each word has `{word, start, end}`. Speaker boundaries come from caption author switches — when the active speaker changes, the previous speaker's segment ends and the new one starts. Text updates from the active speaker confirm they're still talking. Non-active speaker refinements are discarded.

The `speaker-mapper` module (`speaker-mapper.ts`) maps each word to the speaker boundary with most time overlap, producing speaker-attributed segments.
One pipeline on mixed stream. Whisper transcribes everything. Caption speaker changes split output between speakers.

### Components

**Shared pipeline (both platforms use identical code):**

| Component | Role | Key file |
|-----------|------|----------|
| **speaker-streams** | Core buffering, submission, confirmation, emission | `services/vexa-bot/core/src/services/speaker-streams.ts` |
| **transcription-client** | HTTP POST WAV to transcription-service, requests word timestamps | `services/vexa-bot/core/src/services/transcription-client.ts` |
| **transcription-service** | faster-whisper inference, returns segments with word-level timestamps | `services/transcription-service/main.py` |
| **segment-publisher** | Redis XADD + PUBLISH to `tc:meeting:{id}:mutable` channel | `services/vexa-bot/core/src/services/segment-publisher.ts` |
| **transcription-collector** | Consumes Redis stream, persists to Postgres after 30s (persistence only, no mapping/dedup) | `services/transcription-collector/main.py` |
| **api-gateway** | WebSocket (live) + REST (historical) | `services/api-gateway/` |
| **vexa-bot** | Orchestrates everything, platform handlers | `services/vexa-bot/core/src/index.ts` |

**Platform-specific (different approach per platform):**

| Component | Platform | Role | Key file |
|-----------|----------|------|----------|
| **Per-element ScriptProcessors** | Google Meet | N independent AudioContexts, one per `<audio>` element | `index.ts` (`startPerSpeakerAudioCapture`) |
| **Caption Observer + Audio Queue** | Teams | Ring buffer holds mixed audio, captions decide speaker routing | `platforms/msteams/recording.ts` |
| **Speaker Detection (DOM voting)** | Google Meet | MutationObserver on speaking CSS classes, 500ms polling | `platforms/googlemeet/recording.ts` |
| **Speaker Identity Voting** | Google Meet | Correlates audio activity with DOM indicators, locks after 2 votes at 70% | `services/speaker-identity.ts` |
| **speaker-mapper** | Teams | Maps Whisper word timestamps to caption speaker boundaries | `services/speaker-mapper.ts` |

## How

### Implementation Status

**Step 0 (done):** Document architecture.

**Step 1 (done):** Offset-based SpeakerStreamManager.
- `confirmedSamples` pointer tracks confirmed audio, `submitBuffer` sends only unconfirmed
- Offset advances to Whisper's `segment.end` boundary (not full buffer)
- Per-segment stability tracking (2 consecutive matches per segment position) + full-text fallback
- `maxSpeechDurationSec` — Whisper forces segment splits (defaults to server default if env var not set)
- Word-level timestamps from Whisper (`timestamp_granularities=word`)
- Tested: 92.7% content accuracy on 43s monologue, zero boundary artifacts

**Step 2 (done):** Tested on MS Teams via **collection runs** with TTS bots.
- 5 **collection runs**, 18 utterances each across multiple **scenarios**
- Validated: monologue **scenario**, speaker transition **scenario**, short utterance **scenario**, multilingual (Russian)

**Step 3 (done):** Google Meet speaker mapping in bot + right-side refactoring.
- [x] Bot labels Google Meet segments with speaker name locally (using DOM speaking indicators + voting)
- [x] Validate left side: collect core output, verify segment_id + speaker on all segments
- [x] Right side: segment_id flows end-to-end, collector is persistence-only (see [delivery/README.md](delivery/README.md))

### Confidence Filtering

Whisper returns per-segment quality signals (`no_speech_prob`, `avg_logprob`, `compression_ratio`) and per-word `probability`. The pipeline filters hallucinations before they reach the buffer:
- `no_speech_prob > 0.5 && avg_logprob < -0.7` → noise, not speech
- `avg_logprob < -0.8 && duration < 2.0` → hallucinated garbage from silence
- `compression_ratio > 2.4` → repetitive loops

**Scoring**: 18/18 silence hallucinations filtered on 60s dead silence. Zero false positives on real speech.

**Finding (resolved):** Full string match alone never confirmed mid-stream (Whisper output keeps changing slightly as buffer grows). Fixed by implementing per-segment stability tracking: each Whisper segment position is tracked independently, and leading segments that stabilize across `confirmThreshold` consecutive submissions are emitted immediately. Full-text match remains as a fallback for single-segment responses.

### Current Config

Values hardcoded in `index.ts` (around lines 1037-1041). Note: `.env.example` shows different values (3, 3, 3, 120, 15, 15) — the code overrides `submitInterval` to 2s and `confirmThreshold` to 2.

| Parameter | Value (code) | Why |
|-----------|-------------|-----|
| `submitInterval` | 2s | Balance between latency and Whisper efficiency |
| `confirmThreshold` | 2 | 2 consecutive matches per segment position (per-segment stability) |
| `minAudioDuration` | 3s | Don't submit tiny chunks — buffer must have ≥3s unprocessed audio before first submit |
| `maxBufferDuration` | 120s | Trim buffer front at 2 min |
| `idleTimeoutSec` | 15s | High because browser silence filter makes pauses look idle |
| `maxSpeechDurationSec` | undefined (server default) | Only set if `MAX_SPEECH_DURATION_SEC` env var is provided; Whisper forces segment split at this length |

### Verify

**Gate** validation:
1. `make all` from `deploy/compose/`
2. Create a live meeting, send a bot
3. Connect WS, speak, verify live segments with correct speakers
4. `GET /transcripts/{meeting_id}` — same segments
5. Test **scenarios**: monologue >60s, rapid multi-speaker, multilingual

**Sandbox** iteration: see [tests/README.md](tests/README.md) for **replay**, **scoring**, and **collection run** details.

### Platform-Specific Docs

- [Google Meet](google-meet/README.md) — multi-channel, per-element audio, voting/locking
- [MS Teams](ms-teams/README.md) — single-channel, mixed stream, caption-driven labeling

### Testing / Validation

**Speaker identity tests** (`google-meet/tests/speaker-voting/`): 9 scenarios covering dedup guard, voting/locking, and edge cases. 100% accuracy — speaker identity in Google Meet uses `isDuplicateSpeakerName` dedup as the primary guard, with voting as a secondary mechanism.

**E2E pipeline tests** (`google-meet/tests/e2e/`, `ms-teams/tests/e2e/`): Full pipeline from audio capture through transcription to segment delivery, on both platforms.

**Results summary:**
- 18/20 stress test segments captured
- 100% speaker attribution accuracy
- ~15% WER on both platforms (competitive with commercial services on meeting audio)

### Research References

- [Collabora WhisperLive](https://github.com/collabora/WhisperLive) — our codebase ancestor, sliding window server
- [UFAL whisper_streaming](https://github.com/ufal/whisper_streaming) — Local Agreement policy for streaming Whisper
- [WhisperLiveKit](https://github.com/QuentinFuxa/WhisperLiveKit) — SimulStreaming + Streaming Sortformer (SOTA 2025)
- [DiCoW](https://www.sciencedirect.com/science/article/abs/pii/S088523082500066X) — Diarization-Conditioned Whisper
- [Deepgram: Multichannel vs Diarization](https://deepgram.com/learn/multichannel-vs-diarization) — industry comparison

## Development Notes

### Quality Bar

Industry-standard means:
- **Speaker attribution:** every segment attributed to the correct speaker, no "Unknown" speakers
- **Text accuracy:** WER competitive with commercial transcription services
- **Completeness:** no dropped utterances, no phantom/hallucinated segments
- **Latency:** speech-to-segment delivery under 5 seconds
- **Consistency:** WS live segments match REST historical output exactly

### Edge Map

Agent-to-agent boundaries where data crosses:

| Edge | From | To | Data format | Failure mode |
|------|------|----|-------------|--------------|
| Audio capture | Browser (page.evaluate) | Node.js (`handlePerSpeakerAudioData` / `handleTeamsAudioData`) | `(index, number[])` or `(name, number[])` via exposed function | GC collects AudioContext -- no audio arrives |
| Transcription | `TranscriptionClient` | `transcription-service` | HTTP POST multipart WAV | 502/timeout -- buffer grows to hard cap, force-flushes empty |
| Publish | `SegmentPublisher` | Redis stream `transcription_segments` | XADD `{ payload: JSON }` | Redis down -- segments lost |
| Consume | Redis stream | `transcription-collector` | XREADGROUP | Consumer group lag -- delayed delivery |
| Live delivery | `SegmentPublisher` (bot) | `api-gateway` WS | Redis PUBLISH `tc:meeting:{id}:mutable` | No subscribers -- segments in Redis but not on WS |
| Persist | `transcription-collector` background task | Postgres | INSERT after 30s immutability | DB down -- segments stuck in Redis Hash |
| Historical | `api-gateway` REST | Client | JSON merge of Redis Hash + Postgres | Stale data if background task is behind |

### Certainty Table (last updated 2026-03-23)

| Check | Score | Evidence |
|-------|-------|----------|
| Bot joins live meeting | 90 | 3 speakers found and locked |
| Audio reaches TX service | 90 | HTTP 200 with non-empty text |
| Speaker identity locks (TTS) | 90 | All 3 locked permanently at 100% (TTS bots) |
| Speaker identity locks (human) | 40 | 23/215 segments unnamed, lock took 585s for speaker-0 |
| Segment confirmation (GMeet) | 40 | speaker-2 has monolith segments, confirmation never triggers |
| Playback alignment | 50 | Normal segments OK, giant segments seek to wrong position |
| Multi-track dedup | 40 | Same person on 2 tracks produces duplicate content |
| VAD filters silence | 85 | Sandbox: 7 skips on 30s silence gap |
| Language locking | 80 | Schema + API + bot wiring deployed, not tested live |
| Segments in Redis Hash | 90 | 7 segments in DB |
| WS live delivery | 90 | 3/3 segments via WS within 0.1s |
| REST /transcripts | 90 | 3 segments matching WS output |
| WS/REST consistency | 90 | 3/3 WS segments match REST text+speaker+completed |
| End-to-end latency | 90 | 10.8s confirmed (drafts no longer published) |

### How to Test

1. Ensure compose stack is running (`make all` from `deploy/compose/`)
2. Create a live meeting with auto-admit (Teams: `/host-teams-meeting-auto`; GMeet: `gmeet-host-auto.js` + `auto-admit.js`)
3. Send bots to join the meeting (they get auto-admitted through the lobby)
4. Connect to WS: `wscat -c ws://localhost:8056/ws -H "X-API-Key: <token>"`
5. Subscribe to the meeting's transcription channel
6. Speak in the meeting -- verify live segments arrive with correct speaker names
7. Wait 30s+ for immutability threshold
8. Verify `GET /transcripts/{meeting_id}` returns all segments with matching text and speakers
9. Cross-check: every WS segment should appear in REST, same content

Testing uses real live meetings created on-demand via browser sessions -- no mocks.
