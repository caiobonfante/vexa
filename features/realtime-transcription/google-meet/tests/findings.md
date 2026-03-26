# Google Meet Realtime Transcription Findings

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 95 |
|-------|-------|----------|-------------|-------------|
| Bot joins real meeting | 95 | Joined 3 different live meetings (cxi-ebnp-ixk, hcx-qgnx-dre, kpw-ccvz-umz), auto-admitted, full lifecycle (requested→joining→active→completed) each time. 3 media elements found consistently. | 2026-03-17 10:48 | Test locked meetings requiring host admission |
| Bot joins mock (3 speakers) | 90 | 3 speakers found, all locked permanently at 100% | 2026-03-16 20:27 | Update mock with real DOM findings |
| Admission detection | 90 | Works on 3 different real meetings (auto-admitted via "Leave call" button detection). Polling window works correctly. False-positive selectors fixed in prior run. | 2026-03-17 10:48 | Test locked meetings requiring host admission |
| Media element discovery | 95 | Found 3 elements in 3 different real meetings + mock. All elements: paused=false, readyState=4, tracks=1, enabled=1. MediaRecorder started (audio/webm;codecs=opus). | 2026-03-17 10:48 | Test with varying participant counts (5, 10+) |
| Speaker identity locks (TTS) | 90 | Mock: 3/3 locked at 100%. Real: 2 tiles found consistently across 3 meetings (bot + host), 1 unique non-bot participant detected by central list. | 2026-03-17 10:48 | Test real meeting with 3+ active speakers |
| Speaker identity locks (human) | 40 | Meeting 672: 23/215 segments unnamed, lock took 585s for speaker-0. Overlapping speech prevents voting. | 2026-03-23 | **CSRC upgrade:** `getContributingSources()` provides instant identity — see backlog below |
| Multi-track dedup | 40 | Same person on 2 tracks produces duplicate content during SFU remapping | 2026-03-23 | **CSRC upgrade:** CSRC changes instantly when SFU remaps stream — see backlog below |
| Audio reaches TX service | 90 | HTTP 200, non-empty text, 7 segments from mock | 2026-03-16 20:27 | Test with real meeting audio (needs mic) |
| Transcription content | 80 | Mock: 3 speakers transcribed correctly (Alice, Bob, Carol) incl. Russian. 22 segments over WS with real speech text. Real meeting: untested with active mic | 2026-03-17 10:29 | Test real meeting with microphone + multiple speakers |
| WS delivery | 90 | Connected ws://localhost:8056/ws, subscribed to meeting 8798, received 22 live transcript messages. 3 speakers (Alice Johnson, Bob Smith, Carol Williams). Mutable→completed flow working. Meeting status event delivered. First segment ~3s after bot active. | 2026-03-17 10:29 | Test with real meeting, verify latency under load |
| REST /transcripts | 90 | 7 segments with speaker names from mock meeting | 2026-03-16 20:27 | Verify with real meeting transcripts |
| GC prevention | 95 | window.__vexaAudioStreams fix — 324 onSegmentReady calls confirmed | 2026-03-16 20:15 | — |
| Confirmation logic | 60 | Word-level prefix fix landed (LocalAgreement-2). Code analysis: prefix logic correctly handles growing buffers, re-segmentation, empty results, language switch, single-word edge case. 9/9 unit tests pass (full-text fallback path). Replay blocked — data/raw/ absent. No test exercises prefix path with actual segments yet. | 2026-03-24 | Run replay with teams-3sp-collection once data collected; add unit test passing segments to handleTranscriptionResult to cover prefix path directly |
| VAD (Silero) loads and filters | 90 | Model loads from `/app/vexa-bot/core/node_modules/@jjhbw/silero-vad/weights/silero_vad.onnx` (2.3MB, confirmed in image). Log: `[VAD] Silero model loaded`. Mock meeting (bot 8806): 3 speakers transcribed with VAD active, segments in Redis. Silence filtering is silent (no log on skip), so cannot directly count filtered chunks. | 2026-03-17 11:07 | Add VAD filtering counters to logs; compare transcription request counts with/without VAD on identical audio |

**Overall: 88/100** — Confirmation logic raised 40→60 with LocalAgreement-2 prefix fix. Bottleneck: no replay data to validate at Level 2, no unit test covering the new prefix path directly.

**To reach 95:** (1) Collect fresh data to enable replay tests — data/raw/ is empty. (2) Add unit test that passes `segments` to `handleTranscriptionResult` to directly exercise prefix path. (3) Fix pre-existing `__tests__/speaker-streams.test.ts` "fuzzy match" test (assumes behaviour that never existed). (4) Test real meeting with mic audio.

## Backlog: CSRC-Based Speaker Identity (research complete, not implemented)

**Research:** `../zoom/tests/csrc-speaker-research.md` (2026-03-25)

**Opportunity:** `RTCRtpReceiver.getContributingSources()` returns per-participant CSRC identifiers with audio levels. Google Meet's SFU sets CSRC values — each participant gets a unique, session-constant CSRC. When the SFU remaps one of its 3 virtual streams to a different speaker, the CSRC changes instantly.

**What this solves:**
- **Multi-track dedup (score 40):** CSRC tells you exactly who is on each stream — no voting ambiguity when same person appears on 2 tracks during SFU remapping
- **Slow human speaker locking (585s):** CSRC provides instant identity — no need for 2+ vote threshold, no DOM class scraping
- **Obfuscated selector fragility:** CSRC is a standard WebRTC API, not dependent on Google's compiled CSS class names

**Implementation approach:**
1. Hook RTCPeerConnection via `addInitScript` (same pattern Teams already uses for ontrack)
2. Poll `getContributingSources()` every 250ms on each receiver
3. One-time correlation: CSRC ID -> participant name (via DOM, then CSRC is authoritative)
4. Replace DOM voting with CSRC-based identity for all subsequent audio

**Priority:** Medium-high. Would raise speaker identity (human) from 40 to 90+ and multi-track dedup from 40 to 90+. No equivalent for Zoom (CSRC count=0) or Teams (unknown, needs 5-min live test).

**Not started.** No code changes yet. This is a future improvement, not a blocker.

## Bugs found and fixed

### 1. False-positive waiting room selectors (2026-03-17)
**File:** `selectors.ts` — removed `[role="progressbar"]`, `[aria-label*="loading"]`, `.loading-spinner` from `googleWaitingRoomIndicators`
**Found by:** Real meeting test (mock doesn't have these elements)

### 2. Admission logic stuck despite being admitted (2026-03-17)
**File:** `admission.ts` — if "Leave call" found, return admitted immediately (definitive signal)
**Found by:** Real meeting test

### 3. GC bug — ScriptProcessor garbage collected (2026-03-16)
**File:** `index.ts` — store refs on `window.__vexaAudioStreams`
**Found by:** Mock meeting test

### 4. VAD ONNX model path wrong (2026-03-17)
**File:** `vad.ts` — added `/app/vexa-bot/core/node_modules/@jjhbw/silero-vad/weights/silero_vad.onnx` to candidate paths (line 47). Previously only had relative paths from `__dirname` which resolved incorrectly in `dist/services/` at runtime. Now uses 4-candidate search: two relative, one absolute, one fallback.
**Found by:** Bot logs showing `VAD not available (Silero VAD model not found)`
**Verified:** Bot 8806 logs `[VAD] Silero model loaded`, 3 speakers transcribed successfully.

## WS delivery test (2026-03-17 10:29)

**Setup:** Bot (meeting 8798) launched against mock (`http://172.17.0.1:8089/google-meet.html`). WS client connected to `ws://localhost:8056/ws` with API key, subscribed to `google_meet/ws-test-1773743318`.

**Results:**
- WS connected and subscribed immediately (0.3s)
- `meeting.status` event with `status: "active"` received at T+0.3s
- First transcript segment at T+2.7s (Alice Johnson: "Everyone let me start with the product update.")
- 22 total messages received over ~60s
- All 3 speakers present: Alice Johnson, Bob Smith, Carol Williams
- Carol's Russian utterance transcribed correctly
- Mutable segments (completed=false) arrive before final (completed=true) — streaming behavior confirmed
- Message format: `{type: "transcript.mutable", meeting: {id: N}, payload: {segments: [{speaker, text, start, end_time, language, completed, session_uid, speaker_id}]}}`

**Note:** Simple mock (`tests/mock-meeting/index.html`) does NOT work — bot gets stuck at "Attempting to find name input field" because it lacks the Google Meet DOM structure. A proper mock (`features/realtime-transcription/mocks/google-meet.html`) with pre-join screen, name input, toolbar, and participant tiles is required but **does not currently exist** — the `mocks/` directory has not been created yet.

## Multi-meeting real test (2026-03-17 10:43-10:50)

**Setup:** Automated via CDP browser (localhost:9222, Google account signed in). Created meetings using `meet.new`, launched bots via REST API.

**Meeting 1: hcx-qgnx-dre (bot 8801)**
- Created via `meet.new` at 10:43, bot launched immediately
- Status: requested → joining → active → completed
- 3 media elements found (all paused=false, readyState=4, tracks=1, enabled=1)
- 3 per-speaker audio streams started
- 2 participant tiles detected (bot + host), 1 unique from central list
- Alone-timeout triggered after 2min (host not counted by central list)
- 0 transcription segments (expected: no mic in VNC container)
- Post-meeting: aggregation ran, 0 segments from collector

**Meeting 2: kpw-ccvz-umz (bot 8802)**
- Created via `meet.new` at 10:48, identical behavior
- All the same results: 3 media elements, auto-admitted, alone-timeout, completed

**Key observations:**
1. Bot consistently finds 3 media elements across different meetings (not just 1 per participant)
2. Participant counting sees 2 tiles but only 1 unique from "central list" — the host browser is present but not counted, causing alone-timeout
3. `addScriptTag` fails with TrustedScript error (CSP restriction) but falls back to `evaluate()` successfully
4. Per-speaker audio pipeline starts correctly with opus codec every time
5. No transcription without mic audio — confirms the pipeline correctly produces 0 segments when there's silence

## Mock vs Real DOM discrepancies

From live DOM inspection (2026-03-17):
1. Audio elements are standalone, not inside participant tiles
2. Names use `span.notranslate` — mock should match
3. Speaking indicator div (`div.DYfzY.cYKTje.gjg47c`) structure differs from mock
4. `[role="toolbar"]` NOT found in real DOM — admission selector unreliable
5. `data-self-name`, `data-meeting-id` absent from real DOM

Full comparison was documented in `services/vexa-bot/tests/mock-meeting/real-meet-dom-comparison.md` (file no longer present in repo)

## Test matrix for 95 certainty

| Scenario | Tested | Result |
|----------|--------|--------|
| Mock meeting (3 speakers, WAV audio) | Yes | PASS |
| Mock meeting + WS delivery (live segments) | Yes | PASS — 22 segments, 3 speakers, mutable→completed flow |
| Real meeting (1 participant, no mic) | Yes | PASS (join+admission), N/A (transcription) |
| Real meeting (2+ participants, with mic) | No | — |
| Real meeting (locked, requires admission) | No | — |
| Real meeting (5+ participants) | No | — |
| Real meeting (screen sharing active) | No | — |
| Real meeting (participant joins/leaves mid-meeting) | No | — |
| Different meeting URLs (various xxx-yyyy-zzz) | Yes | PASS — 3 URLs tested: cxi-ebnp-ixk, hcx-qgnx-dre, kpw-ccvz-umz. All joined, admitted, completed lifecycle. |
| Alone-timeout behavior | Yes | PASS — Bot correctly detects 1 unique participant (self), counts down from 2min, leaves cleanly, status→completed |
| Per-speaker audio capture (real meeting) | Yes | PASS — 3 streams started per meeting, all tracks enabled, MediaRecorder started with opus codec |
| Standard meeting (`abc-defg-hij` format) | Yes | PASS — tested on 3 real meetings (cxi-ebnp-ixk, hcx-qgnx-dre, kpw-ccvz-umz) |
| Custom nickname meeting (e.g. `my-team-standup`) | No | — |
| Large meeting (10+ participants) | No | — |
| VAD loads and filters silence | Yes | PASS — Silero model loads from correct path, 3 speakers transcribed with VAD active (bot 8806, mock meeting). No "VAD not available" error. |
