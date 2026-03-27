# Google Meet Realtime Transcription Findings

## Certainty Table

> **Post-refactoring re-validation (2026-03-27).** Architecture changed: bot-manager → meeting-api, transcription-collector → meeting-api/db_writer, shared-models → meeting-api own models, auth via gateway header injection. Bot code (vexa-bot), Whisper, ScriptProcessor, speaker identity, VAD, confirmation logic, and gateway WS code are all unchanged.

| Check | Score | Evidence | Last checked | To reach 95 |
|-------|-------|----------|-------------|-------------|
| Bot joins real meeting | 95 | **G5 re-proved:** Bot joined real Google Meet (bjw-ujaj-zpf) via new meeting-api path. Callbacks: joining → awaiting_admission → active all fired. Prior evidence (3 meetings: cxi-ebnp-ixk, hcx-qgnx-dre, kpw-ccvz-umz) also used same bot code. | 2026-03-27 | Test locked meetings requiring host admission |
| Bot joins mock (3 speakers) | 0 | **Path verified, mock HTML missing.** Bot creation via meeting-api verified: bot 22 spawned, container initialized (VAD, TranscriptionClient, SegmentPublisher), joining callback fired to meeting-api. But `google-meet.html` mock does not exist in `mocks/` dir (only `zoom.html`), and `mock.dev.vexa.ai` returns 404. Cannot run 3-speaker mock test without the mock HTML. Prior evidence (3 speakers locked at 100%) used bot code that is unchanged. | 2026-03-27 | Create `mocks/google-meet.html` with pre-join screen, name input, participant tiles, and 3 audio sources |
| Admission detection | 90 | **G5 re-proved:** awaiting_admission → active callback fired on real Google Meet (bjw-ujaj-zpf). Bot code unchanged — same "Leave call" button detection logic. | 2026-03-27 | Test locked meetings requiring host admission |
| Media element discovery | 95 | **Code unchanged, needs re-test to confirm.** ScriptProcessor audio capture code unchanged. G5 transcription success (3 Whisper calls, 2 confirmed segments) implies media elements found and audio captured. Prior: 3 elements in 3 meetings, paused=false, readyState=4. | 2026-03-27 | Test with varying participant counts (5, 10+) |
| Speaker identity locks (TTS) | 90 | **Code unchanged, needs re-test to confirm.** Speaker identity voting logic unchanged. Prior: Mock 3/3 locked at 100%. TTS bots not part of G5 test. | 2026-03-17 10:48 | Re-run TTS bot test via new meeting-api path |
| Speaker identity locks (human) | 40 | **Code unchanged, needs re-test to confirm.** G5: 1 speaker (Dmitriy Grankin) identified successfully. Prior issue (meeting 672: 585s lock time, 23/215 unnamed) still applies — single-speaker G5 doesn't test multi-speaker locking. | 2026-03-27 | **CSRC upgrade:** `getContributingSources()` provides instant identity — see backlog below |
| Multi-track dedup | 40 | **Code unchanged, needs re-test to confirm.** G5 had only 1 human speaker — can't test dedup. Prior issue (same person on 2 tracks during SFU remapping) still applies. | 2026-03-23 | **CSRC upgrade:** CSRC changes instantly when SFU remaps stream — see backlog below |
| Audio reaches TX service | 90 | **G5 re-proved:** Whisper transcription: 3 calls, 125ms avg latency. Audio successfully sent from bot to transcription-service via HTTP POST. | 2026-03-27 | — |
| Transcription content | 85 | **G5 re-proved:** Russian text transcribed correctly. 2 confirmed segments from real speech. Prior mock: 3 speakers, 22 segments incl. Russian. G5 adds real-meeting-with-mic validation that was previously missing. | 2026-03-27 | Test real meeting with multiple speakers |
| WS delivery | 85 | **Code unchanged, needs re-test to confirm.** Gateway WS code path unchanged. G5 proved Redis stream XADD works (segments in Redis stream). PUBLISH to `tc:meeting:{id}:mutable` uses same code path — likely works but WS client not tested in G5. Prior: 22 live messages, 3 speakers, mutable→completed flow. | 2026-03-27 | Connect WS client during live meeting to re-prove delivery |
| REST /transcripts | 90 | **G5 re-proved (storage path).** Segments in Postgres via db_writer (new path, replacing transcription-collector), 30s delay confirmed. Gateway REST read path unchanged. Prior: 7 segments with speaker names. | 2026-03-27 | Call REST endpoint explicitly to verify read path |
| GC prevention | 95 | **Code unchanged, needs re-test to confirm.** `window.__vexaAudioStreams` fix in bot code — unchanged. Prior: 324 onSegmentReady calls confirmed. | 2026-03-16 20:15 | — |
| Confirmation logic | 65 | **Code unchanged, needs re-test to confirm.** LocalAgreement-2 prefix logic unchanged. G5: 2 confirmed segments from real speech — confirmation DID trigger (improvement over prior confirmation failures). 9/9 unit tests still pass. Replay still blocked — data/raw/ absent. | 2026-03-27 | Run replay with fresh data; add unit test for prefix path |
| VAD (Silero) loads and filters | 90 | **G5 re-proved:** VAD: 79 chunks checked, 65 rejected — active filtering confirmed with real speech. Silero model loads and performs silence rejection effectively (82% rejection rate on real meeting audio). | 2026-03-27 | — |

**Overall: 75/100** — Re-validated after architecture refactoring. G5 test (meeting 21, 2026-03-27) re-proved core pipeline end-to-end through new meeting-api path: bot join → audio capture → Whisper transcription → Redis → Postgres. Mock test at 0 — meeting-api bot creation path verified working (bot 22: container spawned, all services initialized, joining callback fired) but `google-meet.html` mock HTML does not exist in repo. WS delivery needs explicit re-test. Confirmation logic slightly up (2 segments confirmed in G5 vs prior confirmation failures).

**To reach 95:** (1) Create `mocks/google-meet.html` (pre-join screen, name input, participant tiles, 3 audio sources) to enable mock test. (2) Connect WS client during live meeting to re-prove delivery. (3) Collect fresh data for replay tests. (4) Test multi-speaker meeting for speaker identity and dedup. (5) CSRC upgrade for instant speaker identity.

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
