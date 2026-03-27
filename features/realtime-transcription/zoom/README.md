# Zoom Realtime Transcription

> **Score: 45/100** — Audio flows (MVP0=80), transcription works with 7% WER (MVP2=60), but speaker identity broken by SFU track remapping (MVP1=30). Auto-admit built but blocked by reCAPTCHA (MVP3=20).
> **Tested:** Audio join, per-speaker ScriptProcessor, DOM speaker polling, transcription pipeline, raw capture, scoring.
> **Not tested:** DOM-based per-segment attribution (MVP1 fix), automated TTS collection (reCAPTCHA blocks).
>
> **Agent manifest:** [CLAUDE.md](.claude/CLAUDE.md) | [findings](tests/findings.md) | [feature-log](tests/feature-log.md)

## Why

Zoom is the third platform (after Google Meet and MS Teams) for the realtime transcription pipeline. All three platforms share the same core pipeline ([SpeakerStreamManager](../README.md#the-shared-pipeline-speakerstreammanager)), but differ in how audio enters the pipeline and how speaker names are resolved.

### Why Browser-Based, Not SDK

The legacy Zoom SDK approach (`services/vexa-bot/core/src/platforms/zoom/strategies/`) uses proprietary native binaries and a completely separate code path. The browser-based approach (`platforms/zoom/web/`) aligns Zoom with GMeet and Teams on the same architecture: Playwright browser, ScriptProcessor audio capture, speaker identity voting, shared SpeakerStreamManager. One codebase, three platforms.

The Zoom Web SDK does not expose raw audio — `mediaCapture` only triggers a recording consent popup. The native Meeting SDK (Windows/Linux/macOS) provides raw audio via C++ callbacks but diverges from the browser architecture. Browser-based per-speaker capture is confirmed working (see [audio architecture research](tests/audio-architecture-research.md)).

### Alternative: Zoom RTMS

Zoom's Realtime Media Streams API (GA since 2025) provides per-participant audio via WebSocket with perfect speaker attribution (`AUDIO_MULTI_STREAMS` mode, OPUS/L16, 48kHz). However, RTMS is read-only (can't speak/chat/share), requires host approval per meeting, and org admin must enable it. It could supplement browser bots for passive transcription but can't replace them for interactive use cases. See [speaker research](tests/speaker-research.md) for full analysis including Recall.ai's approach and diarization alternatives.

## What

### Architecture: Zoom = GMeet Pattern

Live evidence (bot 60) confirmed: **Zoom web client creates separate `<audio>` elements per participant** — identical to Google Meet. Each element has its own MediaStream with a unique audio track. The shared `startPerSpeakerAudioCapture()` pipeline discovers and streams them.

| Aspect | Google Meet | MS Teams | Zoom |
|--------|-----------|----------|------|
| Audio elements | N per-speaker `<audio>` (native) | 1 mixed (RTCPeerConnection hook creates hidden elements) | N per-speaker `<audio>` (native) |
| Speaker identity | DOM voting (speaking indicators) | Caption-driven + DOM fallback | DOM voting (active speaker CSS) + DOM traversal |
| ScriptProcessor pipeline | Yes | Yes | Yes (working) |
| PulseAudio capture | No | No | Yes (parallel fallback path) |
| Key challenge | Obfuscated class names | 1-1.5s caption delay (ring buffer) | Audio channel join + speaker resolution |

Evidence from bot 60:
```
Found 3 active media elements with audio tracks
Element 1: paused=false, readyState=4, tracks=1
Element 2: paused=false, readyState=4, tracks=1
Element 3: paused=false, readyState=4, tracks=1

[PerSpeaker] Stream 0 started (track: d08ef647)
[CONFIRMED] Dmitriy Grankin | "Tak, nu chto u nas Zoom?"
```

### Audio Capture Path

Zoom uses a single audio path: **per-speaker ScriptProcessor** — `index.ts:startPerSpeakerAudioCapture()` discovers `<audio>` elements, creates AudioContext+ScriptProcessor per element. Same pipeline as GMeet. Speaker identity via DOM active speaker polling (250ms).

**PulseAudio does NOT work for Zoom audio capture** — Chrome routes Zoom WebRTC audio through WebAudio API internally, not PulseAudio. The WhisperLive dual pipeline was removed (~140 lines from recording.ts) after confirming PulseAudio records all zeros.

### Zoom SFU 3-Stream Limit

Zoom's SFU delivers only 3 audio streams to any client, regardless of participant count. This is identical to Google Meet's architecture. Key implications:

- With >4 participants, some speakers get NO audio track
- Tracks remap dynamically as active speakers change (track 0 = Charlie, then later track 0 = Alice)
- **Permanent track locking is incompatible** — track-to-speaker binding changes over time
- The recorder bot occupies 1 of 3 tracks, leaving only 2 for actual speakers
- Fix: DOM-based per-segment attribution (use active speaker CSS polling to label segments as they arrive)

### MVP Ladder

Each MVP follows the [validation cycle](../tests/README.md): **collection run** (live meeting with TTS bots, script = ground truth) → **sandbox iteration** (replay collected data offline, score, fix, re-score) → **expand** (new scenarios when plateaued). The goal is to reach the sandbox as fast as possible — that's where cheap iteration happens.

#### MVP0 — Audio Channel Join

**Gate:** Bot joins Zoom meeting, non-silent audio in `<audio>` elements (amplitude > 0.005).

**What to build:** Fix join.ts (click "Allow" not "Continue without") + harden prepare.ts audio join flow.

**How to validate:**
1. Deploy: rebuild bot container (`docker compose build vexa-bot`)
2. Collection run (Level 4 — human hosts meeting, admits bot manually):
   - Human creates Zoom meeting, shares URL
   - POST /bots with meeting URL → human admits bot through waiting room
   - Bot logs capture: audio permission grant, audio join confirmation, media element discovery, amplitude readings
3. Pass: logs show `"Granted audio permission"`, `"Joined with Computer Audio"`, `"Found N media elements"` with amplitude > 0.005
4. Fail: iterate — read logs, diagnose, fix code, redeploy, re-run

**Status:** Code fix written (join.ts + prepare.ts). Needs deploy + Level 4 validation.

**No sandbox possible yet** — need audio flowing before anything can be collected or replayed.

#### MVP1 — Speaker Identity Resolution

**Gate:** Per-speaker streams labeled with correct participant names. Tracks lock within 30s.

**What to build:** Verify/fix `resolveZoomSpeakerName()`. Path 2 (`queryZoomActiveSpeaker`) is primary. Path 1 (`traverseZoomDOM`) is likely dead code.

**How to validate:**
1. Level 1 (mock — cheap): test against `mocks/zoom.html` in Playwright. Run `startPerSpeakerAudioCapture()`, verify voting/locking works with 3 mock speakers cycling active speaker. No live meeting needed.
2. Level 4 (live — expensive): same meeting as MVP0 with 2+ speakers. Check bot logs for `"Track N → 'Name' LOCKED PERMANENTLY"` events.

**Status:** Blocked by MVP0. Mock page ready for Level 1 testing.

#### MVP2 — End-to-End Transcription + First Collection Run

**Gate:** Confirmed segments in Redis with correct speaker names. First Zoom dataset collected.

**What to build:** Resolve dual-path conflict (per-speaker ScriptProcessor vs PulseAudio+WhisperLive). Shared pipeline should work automatically once MVP0+MVP1 are done.

**How to validate — this is the first collection run:**
1. Level 4: human hosts Zoom meeting, sends recorder bot + speaks known phrases (the **script** = **ground truth**)
2. Bot captures all **collected data** during meeting:
   - Per-speaker audio WAVs (from ScriptProcessor pipeline)
   - Speaker events (SPEAKER_START/END from DOM polling, with timestamps)
   - CONFIRMED segments (from SpeakerStreamManager)
   - Pipeline output (Redis segments, Postgres rows)
3. Export collected data to `data/raw/zoom-first-collection/`:
   - Audio files, speaker events JSON, ground truth JSON, bot logs
4. Score: `python3 score-e2e.py results/` → WER, speaker accuracy, completeness

**After MVP2, the sandbox opens:**
```
make play-replay DATASET=zoom-first-collection
```
Change code → replay → re-score in seconds. No meeting needed. This is where cheap iteration begins.

**Status:** Blocked by MVP1.

#### MVP3 — Automated Collection Runs (THE INFLECTION POINT)

**Gate:** TTS bots join Zoom autonomously, speak scripted ground truth, collection runs are fully automated. No human in any meeting ever again.

**What to build:**
1. `zoom-auto-admit.js` — recorder bot polls participants panel, clicks "Admit All" (mirrors `auto-admit.js` for GMeet)
2. `zoom-host-auto.js` OR Zoom REST API instant meeting creation (no waiting room)
3. Fix TTS bot ejection (~4s) — removal.ts false-positive from framenavigated

**How to validate:**
1. Run automated collection: `bash tests/e2e/test-e2e.sh` (no `--meeting` flag — creates its own)
2. Script sends 3 TTS bots (Alice, Bob, Charlie) with 9 ground truth utterances
3. Collects raw data automatically → `data/raw/zoom-3sp-basic/`
4. Scores automatically → pass criteria: speaker accuracy >= 90%, completeness >= 80%, WER <= 30%

**After MVP3, the validation cycle runs autonomously:**
```
 COLLECTION RUN (automated)              SANDBOX (inner loop)
 ──────────────────────────              ────────────────────
 TTS bots speak from script              Replay collected data offline
 Script = ground truth                   Feed through pipeline (real Whisper)
 Collect: audio, speaker events,         Score against ground truth
   pipeline output                       Change code, replay, re-score
         │                                         │
         │  export collected data                  │  plateau?
         └──────────────►──────────────────────────┘  need new scenarios?
                                         │
                                         └──► new script → new collection run
                                              → new collected data → sandbox
```

**Status:** Blocked by MVP2.

#### MVP4 — Quality Parity with GMeet/Teams

**Gate:** WER < 15%, speaker attribution > 95%, latency < 5s.

**How to validate (all sandbox — cheap):**
1. Replay existing datasets: `make play-replay DATASET=zoom-3sp-basic`
2. Expand: design adversarial scripts (overlapping speech, silence gaps, short phrases, fast transitions)
3. New automated collection runs with adversarial scripts → new datasets
4. Replay new datasets → diagnose-fix cycle
5. Compare against GMeet/Teams benchmarks on same ground truth scripts

**Status:** Blocked by MVP3.

#### MVP5 — Production Hardening

**Gate:** Reliable across all meeting types, URL formats, edge cases. Production-ready.

**How to validate (cheapest — no meetings):**
1. Level 0: property tests — random meeting URLs through `buildZoomWebClientUrl()`
2. Level 1: chaos — kill transcription-service mid-stream, disconnect Redis, simulate network jitter
3. Level 3: soak — automated 2-hour meeting via MVP3 infrastructure, verify no memory leaks
4. URL coverage: `zoom.us/j/`, `us05web.zoom.us/j/`, `events.zoom.us/ejl/`, vanity URLs, personal meeting IDs

**Status:** Blocked by MVP4.

#### Testing Cost Progression

```
MVP0: Level 4 only (human hosts meeting)          ████████████████ L4 EXPENSIVE
MVP1: Level 1 (mock) + Level 4 (live)             ████████████ L1+L4
MVP2: First collection run → sandbox opens         ████████ L2+L4
MVP3: Automated collection → sandbox dominates     ████ L2+L3 INFLECTION
MVP4: Sandbox only (replay + expand)               ██ L2 CHEAP
MVP5: Level 0+1 (property + chaos)                 █ L0+L1 CHEAPEST
```

### Data Stages

Same pipeline stages as the parent feature (see [realtime-transcription data stages](../README.md#data-stages-and-iteration-cost)). Zoom-specific datasets will live in `data/raw/zoom-*` once MVP3 produces them.

### Components

**Shared pipeline (same code as GMeet/Teams):**

| Component | Role | Key file |
|-----------|------|----------|
| **speaker-streams** | Core buffering, submission, confirmation, emission | `services/vexa-bot/core/src/services/speaker-streams.ts` |
| **transcription-client** | HTTP POST WAV to transcription-service | `services/vexa-bot/core/src/services/transcription-client.ts` |
| **transcription-service** | faster-whisper inference | `packages/transcription-service/main.py` |
| **segment-publisher** | Redis XADD + PUBLISH | `services/vexa-bot/core/src/services/segment-publisher.ts` |
| **transcription-collector** | Consumes Redis stream, persists to Postgres | `services/transcription-collector/main.py` |

**Zoom-specific:**

| Component | Role | Key file | Status |
|-----------|------|----------|--------|
| **Join flow + URL builder** | Navigate to Zoom web client, enter meeting | `platforms/zoom/web/join.ts` | Working (click "Allow" fix applied) |
| **Pre-meeting prep** | Join audio channel, dismiss dialogs | `platforms/zoom/web/prepare.ts` | Working (8-retry audio join) |
| **Admission detection** | Detect waiting room vs meeting entry | `platforms/zoom/web/admission.ts` | Working |
| **Recording (DOM polling)** | Speaker polling (250ms) for attribution | `platforms/zoom/web/recording.ts` | Working (WhisperLive removed) |
| **Removal monitoring** | Detect bot ejection via framenavigated | `platforms/zoom/web/removal.ts` | Working (grace period + allowlist fix) |
| **Leave flow** | Clean exit | `platforms/zoom/web/leave.ts` | Working |
| **DOM selectors** | CSS selectors for Zoom web UI | `platforms/zoom/web/selectors.ts` | Verified from live DOM |
| **Speaker identity** | Zoom-specific name resolution (2 paths) | `services/speaker-identity.ts` (zoom handler) | DOM polling works, track locking broken |
| **Raw capture** | Per-speaker WAV dumping + events.txt | `services/raw-capture.ts` | Working |
| **Auto-admit** | Admit bots from waiting room | `scripts/zoom-auto-admit.js` | Built, untested (reCAPTCHA) |
| **Host automation** | Headless Zoom meeting hosting | `scripts/zoom-host-auto.js` | Built, untested (reCAPTCHA) |
| **Zoom mock** | 3-speaker mock for offline testing | `mocks/zoom.html` | Working |
| **Scoring** | WER + speaker accuracy scoring | `zoom/tests/score-zoom.py` | Working (--post-fix, --merge) |

## How

### Current Status

**MVP0 DONE (score 80). MVP2 partially working (score 60). MVP1 is the primary blocker (score 30).**

Audio flows after "Allow" click fix. Transcription pipeline produces segments with 7% WER. But speaker attribution is broken: Zoom SFU remaps tracks dynamically, making permanent track locking assign wrong names. Next step: replace track locking with DOM-based per-segment attribution.

### Known Blockers (Priority Order)

1. **Track locking vs SFU remapping** (MVP1, PRIMARY) — Zoom SFU delivers only 3 audio streams, remaps dynamically. Permanent track locking assigns wrong names. Fix: DOM-based per-segment attribution using active speaker CSS polling (already working at 250ms).

2. **reCAPTCHA on rapid joins** (MVP3) — Zoom shows CAPTCHA after 3-4 rapid bot joins from same IP. Blocks automated TTS testing. Mitigations: stagger joins 30s+, use authenticated Zoom sessions, or Zoom REST API for instant meeting creation.

3. **SFU 3-stream limit drops speakers** (MVP1/MVP2) — With recorder + 3 TTS speakers + host = 5 participants, only 3 audio tracks delivered. Some speakers get no track. Fix: ensure recorder doesn't occupy a track (mute), or accept dynamic coverage.

4. **Recorder misattributed as speaker** (MVP2) — Some segments attributed to "Vexa Recorder". Need to filter recorder from speaker attribution.

### Verify

**Gate validation:**
1. `make all` from `deploy/compose/`
2. Create a Zoom meeting, send a bot
3. Check bot logs for "Joined with Computer Audio" and non-silent amplitude (> 0.005)
4. Connect WS, verify live segments arrive with correct speakers
5. `GET /transcripts/{meeting_id}` — same segments
6. Test scenarios: monologue >60s, rapid multi-speaker, multilingual

### Code Locations

| Component | File | Status |
|-----------|------|--------|
| Meeting flow orchestrator | `platforms/shared/meetingFlow.ts` | Shared, working |
| Zoom web entry point | `platforms/zoom/web/index.ts` | Working |
| Join flow + URL builder | `platforms/zoom/web/join.ts` | Working ("Allow" click fix applied) |
| Pre-meeting prep + audio join | `platforms/zoom/web/prepare.ts` | Working (8-retry audio join) |
| Admission detection | `platforms/zoom/web/admission.ts` | Working |
| Recording (DOM polling) | `platforms/zoom/web/recording.ts` | Working (WhisperLive removed) |
| Removal monitoring | `platforms/zoom/web/removal.ts` | Working (grace period + allowlist fix) |
| Leave flow | `platforms/zoom/web/leave.ts` | Working |
| DOM selectors | `platforms/zoom/web/selectors.ts` | Verified from live DOM |
| Speaker identity (shared) | `services/speaker-identity.ts` | DOM polling works, track locking broken |
| Per-speaker audio capture (shared) | `index.ts:startPerSpeakerAudioCapture()` | Working for Zoom |
| Raw capture | `services/raw-capture.ts` | Working (WAV + events.txt) |
| Auto-admit | `scripts/zoom-auto-admit.js` | Built, untested |
| Host automation | `scripts/zoom-host-auto.js` | Built, untested |
| Zoom mock | `mocks/zoom.html` | Working (3 speakers) |
| Scoring | `zoom/tests/score-zoom.py` | Working |

### Dead Ends

- **PulseAudio-based audio capture for Zoom transcription:** Chrome doesn't route Zoom WebRTC audio through PulseAudio. Records all zeros (39MB WAV of silence confirmed). Per-speaker ScriptProcessor is the only working path.
- **Permanent track locking for Zoom:** SFU remaps tracks dynamically. Track 0 is Charlie one moment, Alice the next. Locking assigns wrong names permanently. Need DOM-based per-segment attribution.
- **Zoom Web SDK raw audio access:** The Web SDK does not expose raw audio/video data. `mediaCapture` only triggers recording consent popup. Only the native Meeting SDK provides raw audio access.
- **Testing TTS bots without auto-admit:** Bots stuck in waiting room or ejected in ~4s. Must either disable waiting room or implement auto-admit before TTS testing is meaningful.
- **Rapid sequential bot joins from same IP:** Zoom shows reCAPTCHA (size=normal) after 3-4 rapid joins. Cannot brute-force automated testing.

### External APIs

- **Zoom RTMS (Realtime Media Streams):** GA since 2025. Per-participant audio via WebSocket (`AUDIO_MULTI_STREAMS` mode, OPUS/L16, 48kHz). Perfect speaker attribution via `onActiveSpeakerEvent`. Read-only (can't speak/chat), requires host approval + org admin enable. Could supplement browser bot for passive transcription. [Docs](https://developers.zoom.us/docs/rtms/) | [SDK](https://github.com/zoom/rtms)
- **Zoom Meeting SDK (native):** Per-participant raw audio via C++ callbacks. Full bidirectional. Proprietary licensing, diverges from browser architecture.

### Comparison with Siblings

| Metric | GMeet | Teams | Zoom (current) |
|--------|-------|-------|----------------|
| Overall score | 70 | 65 | 45 |
| Audio capture | 90 (per-speaker ScriptProcessor) | 90 (mixed + caption routing) | 80 (per-speaker ScriptProcessor, working) |
| Speaker identity | 90 (TTS), 40 (human) | 90 (caption-driven) | 30 (DOM polling works, track locking broken) |
| Transcription | 90 | 90 | 60 (segments flow, 7% WER, wrong speakers) |
| Auto-admit | Yes (gmeet-host-auto.js) | Yes (/host-teams-meeting-auto) | Built, untested (reCAPTCHA) |
| TTS testing | Yes | Yes | Blocked (reCAPTCHA + SFU limits) |
| Testing cost | Cheap (TTS replay) | Cheap (TTS replay) | Medium (raw-capture enables offline analysis) |

### Research References

- [Audio architecture research](tests/audio-architecture-research.md) — live evidence that Zoom uses per-speaker `<audio>` elements (GMeet pattern), correcting initial mixed-audio assumption
- [Speaker attribution research](tests/speaker-research.md) — RTMS, native SDK, pyannote diarization, WhisperX, DOM-based approach, Recall.ai's dual strategy
- [Collabora WhisperLive](https://github.com/collabora/WhisperLive) — codebase ancestor, sliding window server
- [How Zoom's web client avoids using WebRTC](https://webrtchacks.com/zoom-avoids-using-webrtc/)
- [Recall.ai: Zoom Web SDK raw audio](https://www.recall.ai/blog/can-i-access-raw-audio-data-using-the-zoom-web-sdk)
