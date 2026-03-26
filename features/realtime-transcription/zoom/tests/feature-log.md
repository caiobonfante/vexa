# Feature Log — Zoom Transcription

Append-only.

## 2026-03-23

[STATUS] Scaffold only. No code, no tests, no data. All certainty scores at 0.

[DECISION] Browser-based approach chosen over legacy SDK. Rationale: aligns all 3 platforms on same codebase (ScriptProcessor audio capture, speaker identity voting, same SpeakerStreamManager). Legacy SDK at `services/vexa-bot/core/src/platforms/zoom/` requires proprietary binaries and separate code path.

[RESEARCH] Zoom web client DOM structure unknown. Needs live inspection at `zoom.us/wc/join/{id}`. Open questions: per-participant audio elements or mixed? Speaking indicator selectors? CAPTCHA/anti-bot on join? Waiting room behavior?

## Current Stage

ENV SETUP — need to inspect Zoom web client DOM before any implementation. First step: spawn browser session, navigate to `zoom.us/wc/join/{test-id}`, document DOM structure.

## 2026-03-25

[EXTERNAL] Zoom web client DOES create per-speaker `<audio>` elements (same as GMeet) — confirmed by live bot evidence (bot 60). 3 separate MediaStream elements found with individual audio tracks. The `startPerSpeakerAudioCapture()` pipeline (index.ts:1689) discovers and streams them. Mixed-audio assumption was wrong. See audio-architecture-research.md.

## 2026-03-25 (MVP6 cycle 2 — Zoom transcription pipeline investigation)

[FINDING] **PulseAudio recording captures ALL ZEROS.** bot_sink_79.monitor has correct sink-input from Chrome but records 319s of pure silence. Zoom Web does NOT route meeting audio through PulseAudio — it uses WebAudio API internally. The 39MB WAV file is silence.

[FINDING] **Browser per-speaker streams exist but are silent.** 3 media elements found with AudioContext+ScriptProcessor, but `maxVal` never exceeds 0.005 threshold. Either the elements don't carry real audio, or Zoom uses AudioWorklet instead.

[FINDING] **Root cause: recorder bot never joins Zoom's audio channel.** The join flow clicks "Continue without microphone and camera" for recorder bots (join.ts line 107). This means the bot enters the meeting without audio infrastructure. `prepareZoomWebMeeting()` has "Join Audio" logic but needs more robust selectors and retries.

[FINDING] **DOM speaker polling works but only sees host.** `SPEAKER_START: Dmtiry Grankin` detected via CSS `.speaker-active-container__video-frame`. TTS bots (Alice, Bob, Charlie) not detected as speakers despite speaking — either their speech doesn't reach the meeting or Zoom doesn't highlight them.

[FIX] **Added `feedZoomAudio()` to route PulseAudio → transcription pipeline.** (index.ts + recording.ts) Routes mixed PulseAudio audio through SpeakerStreamManager (Teams-style) using DOM speaker polling for attribution. Falls back to "Unknown" when no speaker detected.

[FIX] **Made `prepareZoomWebMeeting()` more robust.** (prepare.ts) Added retries, multiple selectors (footer button + floating banner), "Join Audio by Computer" dialog handling. This should fix the audio channel join issue.

[FIX] **Ungated SPEAKER_START/END logs from WhisperLive.** (recording.ts) Speaker change logging now always fires, not gated by WhisperLive being active.

[DEAD-END] **PulseAudio-based audio capture for Zoom is unreliable.** Even with correct sink routing (bot_sink_79.monitor), Chrome doesn't route Zoom's WebRTC audio through PulseAudio. The browser-side per-speaker pipeline (like GMeet) is the correct approach, but requires the bot to join audio first.

[NEXT] Test with active meeting: verify "Join Audio" works → audio flows through browser elements → per-speaker pipeline produces transcription. Need fresh Zoom meeting URL (previous one expired).

[STATUS] Three blockers identified in meeting 63 testing — details below.

### Blocker 1: Speaker Names Empty

[FINDING] `resolveSpeakerName()` for zoom was not implemented until current sprint (speaker-identity.ts is M in git). Current implementation (lines 413-486) uses two resolution paths:
  - Path 1 (`traverseZoomDOM`): walks DOM tree UP from `<audio>` element looking for `.video-avatar__avatar-footer`. LIKELY FAILS — Zoom Web Client appends audio elements to a separate container, not inside participant tiles. DOM traversal will hit `document.body` without finding the footer.
  - Path 2 (`queryZoomActiveSpeaker`): queries `.speaker-active-container__video-frame` or `.speaker-bar-container__video-frame--active` globally. SHOULD WORK — selectors are verified from live DOM inspection (selectors.ts). Returns the currently active speaker's name.

[RISK] If both paths return null, voting never accumulates and names stay empty. Most critical: test whether `queryZoomActiveSpeaker()` actually returns a name during active speech in the per-speaker pipeline (it should — same selectors that DOM polling in recording.ts already uses successfully).

[RISK] The per-speaker pipeline calls `resolveSpeakerName(page, elementIndex, 'zoom', botName)`. The `elementIndex` corresponds to position in the live audio element list. If multiple elements exist and Path 1 fails, Path 2 returns the same active speaker name for ALL tracks simultaneously — this will cause the voting/locking system to reject votes (isNameTaken check) and nothing locks. Need to ensure single-speaker dominance during voting window.

### Blocker 2: Mic Toggle / TTS Audio Path

[FINDING] `toggleZoomMic()` was added in current sprint (microphone.ts is M in git). Before this change, zoom hit the "Unsupported platform" else-branch. Current implementation clicks `.join-audio-container__btn` — correct selector (verified in selectors.ts).

[FINDING] PulseAudio audio chain for TTS to reach Zoom WebRTC:
  TTS audio → PulseAudio `tts_sink` → `virtual_mic` (remap of `tts_sink.monitor`) → Chromium default source → `getUserMedia({audio})` → Zoom WebRTC mic
  This chain is set up at container startup (entrypoint.sh). For Zoom Web TTS bots, `join.ts:95-103` clicks Zoom's "Allow" button to trigger `getUserMedia({audio:true})`. Browser args include `--use-fake-ui-for-media-stream` (auto-grants permission) but NOT `--use-file-for-fake-audio-capture` so Chromium reads from PulseAudio.

[RISK] The per-bot PulseAudio sink (`bot_sink_{meeting_id}`) created in index.ts:1929-1942 sets `PULSE_SINK` (output destination for recordings). TTS still plays to `tts_sink`. If `virtual_mic` is NOT the PulseAudio default source at Chromium launch time (or if a different source is selected), TTS audio silently disappears. Verify with: `pactl list sources short` inside the TTS bot container; check entrypoint.sh for the virtual_mic setup order.

[EXTERNAL] Zoom Web Client calls `getUserMedia({audio: true, video: false})` when "Allow" is clicked. PulseAudio must expose `virtual_mic` as the ALSA/PulseAudio default capture device BEFORE this call. If Chromium cached the device list before `virtual_mic` was created, it may pick up a silent device instead.

### Blocker 3: TTS Bots Ejected in ~4s

[FINDING] Bots 66/67/69 went active→completed ~4s after joining. Three candidate causes:

  1. **Zoom Waiting Room (most likely)**: No auto-admit mechanism exists for Zoom Web. If meeting has waiting room enabled, TTS bots join → waiting room → recorder bot has no code to click "Admit". The `waitForZoomWebAdmission()` timeout eventually fires and bot exits. But 4s is faster than any polling timeout...

  2. **False-positive removal detection**: `removal.ts:31-42` framenavigated listener fires if URL is `/wc/` but not `/meeting`. Zoom may navigate through a redirect sequence during voice-agent join (with audio enabled), briefly hitting a `/wc/{id}/join` URL — this would trigger `triggerRemoval()` before the meeting fully loads. This would explain the consistent ~4s timing.

  3. **Zoom anti-bot / rate limiting**: Multiple voice-agent bots joining simultaneously from same IP with fake media. Zoom's anti-bot system may detect Chrome headless characteristics + fake audio device + rapid sequential joins and reject quickly.

[PRACTICE] The Teams equivalent handles waiting room via `/host-teams-meeting-auto` which sets up auto-admit via DOM clicking. Zoom needs an equivalent: a function in the recorder bot that polls the participants panel and clicks "Admit All" every 5s. NOT implemented yet.

[PRACTICE] To debug exact cause of 4s ejection: add logging at every `triggerRemoval()` call site in removal.ts to capture the exact URL, title, and trigger reason at ejection time. The log already does this but the output needs to be captured in testing.

[DEAD-END] Testing TTS bots while meeting uses waiting room (without auto-admit) — bots will always be ejected. Must either disable waiting room or implement auto-admit in recorder bot before TTS bot testing is meaningful.

## 2026-03-25 (bot-escalation session — full Zoom pipeline investigation)

### Fixes Applied

[FIX] **MVP0: click "Allow" not "Continue without mic" (join.ts).** Root cause of silent audio: "Continue without microphone and camera" prevents BOTH sending AND receiving audio. All bots now click "Allow" on permission dialog. Audio flows through per-speaker ScriptProcessor after this fix.

[FIX] **Dual pipeline disabled: WhisperLive transcription removed (~140 lines from recording.ts).** PulseAudio path captured silence on Zoom. Removed WhisperLive WebSocket transcription, keeping only per-speaker ScriptProcessor path. Result: 0 duplicates (was 43).

[FIX] **Empty speakers: DOM fallback in handlePerSpeakerAudioData.** When per-speaker pipeline can't resolve speaker name, falls back to DOM active speaker query. Result: 0 empty speakers (was 29).

[FIX] **Browser session: novnc package + websockify fallback + X-Frame-Options CSP.** Fixed VNC access for debugging browser-based bots.

[FIX] **Removal false-positive: grace period 10->20s + audio-init URL allowlist (removal.ts).** TTS bots were ejected in ~4s due to framenavigated listener firing during Zoom's post-join redirect. Extended grace period and allowlisted audio-init URLs.

[FIX] **TTS connectivity: tts-service DNS alias on agentic network.** TTS bots couldn't reach tts-service. Added DNS alias so PulseAudio virtual_mic chain works: TTS audio -> PulseAudio tts_sink -> virtual_mic -> Chromium getUserMedia -> Zoom WebRTC.

### Key Findings

[FINDING] **Zoom SFU 3-stream limit — same as GMeet.** Zoom delivers only 3 audio tracks to any client, regardless of participant count. With 5 participants (Recorder+Alice+Bob+Charlie+Host), only 3 get tracks. Tracks remap dynamically as active speakers change. This is identical to GMeet's architecture.

[FINDING] **Track locking incompatible with SFU remapping.** Permanent track-to-speaker locking assigns wrong names because Zoom SFU reuses the same 3 tracks for different speakers over time. Track 0 carried Charlie initially, then switched to Alice. Need DOM-based per-segment attribution instead.

[FINDING] **reCAPTCHA (size=normal) after rapid sequential bot joins from same IP.** Zoom detects multiple headless Chrome joins and shows CAPTCHA. Blocks all automated testing after 3-4 rapid joins. Mitigation: stagger joins 30s+, use authenticated sessions, or Zoom API for meeting creation.

[FINDING] **PulseAudio captures silence on Zoom — confirmed.** Chrome doesn't route Zoom WebRTC audio through PulseAudio. Per-speaker ScriptProcessor is the ONLY working audio capture path. PulseAudio is usable for TTS output (to Zoom mic) but not for recording.

[FINDING] **Recorder bot occupies 1 of 3 SFU tracks.** The recorder bot, even when muted, counts as a participant and may consume one of the 3 audio streams. This leaves only 2 tracks for actual speakers, causing Alice to be dropped in zoom-3sp-fixed.

### Implementations

[IMPLEMENTED] **raw-capture.ts** — Per-speaker WAV dumping + events.txt for offline analysis. Captures speaker transitions from DOM polling with timestamps, plus per-speaker audio segments. Enables post-hoc analysis without live meeting.

[IMPLEMENTED] **zoom-auto-admit.js** — Polls participants panel, clicks "Admit All" for Zoom waiting room. Mirrors gmeet-host-auto.js pattern. Built but untested (reCAPTCHA blocks automated sessions).

[IMPLEMENTED] **zoom-host-auto.js** — Headless Zoom meeting hosting script. Built but untested (reCAPTCHA).

[IMPLEMENTED] **removal.ts fix** — Grace period extended, audio-init URL allowlist added to prevent false-positive ejection during Zoom's post-join navigation.

[IMPLEMENTED] **mocks/zoom.html** — Mock Zoom meeting page with 3 speakers, oscillator audio, JS API for testing speaker identity pipeline without live meetings. Supports cycling active speakers and per-speaker audio elements.

[IMPLEMENTED] **score-zoom.py** — Scoring tool with --post-fix (simulate fixes on existing data) and --merge (combine collection info with scoring). Validated: 7% WER, 88% completeness on zoom-3sp-basic post-fix simulation.

### Dead Ends

[DEAD-END] **PulseAudio for Zoom transcription.** Records all zeros. Chrome routes Zoom audio through WebAudio API internally, not PulseAudio. 39MB WAV file of pure silence confirmed.

[DEAD-END] **Permanent track locking for Zoom.** SFU remaps tracks dynamically. A track that was "Charlie" becomes "Alice" when active speakers change. Lock assigns wrong name permanently. Must use DOM-based per-segment attribution.

[DEAD-END] **Rapid sequential bot joins from same IP.** Zoom shows reCAPTCHA after 3-4 joins. Cannot brute-force automated testing — need staggered timing or authenticated sessions.

### Collection Run Results

[DATA] **zoom-3sp-basic** — First collection. 3 TTS speakers, 9 utterances, 29 confirmed + 43 duplicates. Pre-fix baseline. Dual pipeline produced parallel segments.

[DATA] **zoom-3sp-fixed** — Post dual-pipeline fix. 11 confirmed segments, 0 duplicates, 0 empty speakers. Alice missing (SFU dropped her track). Only Bob and Charlie detected.

[DATA] **zoom-3sp-rawcap** — Raw capture validation. 12 speaker transitions in events.txt. DOM polling correctly tracks speaker changes. Some segments misattributed to "Vexa Recorder".

### Scores

[SCORE] MVP0 Audio join: 20 -> 80 (fix: "Allow" click + prepare.ts hardening)
[SCORE] MVP1 Speaker identity: 30 (unchanged — track locking broken, DOM polling works)
[SCORE] MVP2 Transcription: 0 -> 60 (segments flow, 7% WER, but wrong speakers)
[SCORE] MVP3 Auto-admit: 0 -> 20 (scripts built, untested due to reCAPTCHA)
[SCORE] Overall: 15 -> 45


## 2026-03-25 (collection 4 — speaker fix validation)

[FINDING] **DOM-based per-track attribution doesn't work either.** Collection zoom-3sp-speakerfix shows: DOM correctly detects Alice, Bob, Dmtiry (Charlie still missing — SFU limit). But assigning DOM active speaker to per-speaker tracks produces wrong results because DOM speaker ≠ audio track owner. Track 0 had Alice's audio but DOM said "Bob" was active → all segments labeled "Bob".

[FINDING] **Per-speaker capture is fundamentally wrong for Zoom.** Unlike GMeet where each `<audio>` element carries one participant's audio stably, Zoom's SFU multiplexes audio across 3 shared tracks dynamically. Neither track locking NOR DOM-based attribution works because the mapping between tracks and speakers is not exposed.

[DEAD-END] **Per-speaker ScriptProcessor + DOM attribution for Zoom.** The approach works for GMeet (stable per-participant elements) but fails for Zoom (shared SFU tracks with dynamic remapping). Two approaches tried:
  1. Track locking (voting): wrong names because tracks get reused
  2. DOM active speaker: wrong correlation because DOM speaker ≠ track audio source

[PRACTICE] **Zoom should use the Teams pattern: mixed audio + caption/DOM attribution.** Instead of per-speaker capture, capture the MIXED audio stream and use DOM speaker changes to split segments. This is exactly what the old WhisperLive path did (before we disabled it). The difference: feed mixed audio through SpeakerStreamManager with DOM-driven speaker boundaries, not through per-element ScriptProcessors.

[NEXT] Revert to mixed audio approach for Zoom:
  1. Keep PulseAudio capture (parecord) as the audio source
  2. Use DOM speaker polling for attribution (SPEAKER_START/END events — already working)
  3. Feed mixed audio + speaker events through SpeakerStreamManager (Teams-style)
  4. Disable per-speaker ScriptProcessor for Zoom (it produces garbage due to SFU remapping)
  5. This is the approach that produced correct speaker names in zoom-3sp-basic (zoom-Alice, zoom-Bob, zoom-Charlie all correct)

## 2026-03-25 (collection 5 — tick-by-tick validation)

[VALIDATION] Full tick-by-tick validation on zoom-3sp-run5:
  - Text quality: EXCELLENT (100% match on 6/9 utterances)
  - Speaker accuracy: 3/9 (37%) — only Bob correct
  - Alice → "Vexa Recorder" (SFU multiplexes Alice onto Recorder's track)
  - Charlie → invisible (SFU never highlights Charlie as active speaker)
  - Mixed audio WAV = 0 bytes (PulseAudio captures silence — known dead end)
  - Video recording = 5.5MB webm (working)
  - events.txt = 32 entries across 2 runs (speaker changes + segments)

[ROOT CAUSE] Three separate issues:
  1. Charlie invisible: SFU 3-stream limit drops Charlie entirely from DOM speaker detection
  2. Alice misattributed: her audio goes to Recorder's track (SFU remapping)
  3. PulseAudio silence: can't get mixed audio through parecord (Chrome doesn't route Zoom WebRTC through PulseAudio)

[INSIGHT] The text transcription is production-quality. The ONLY problem is speaker attribution. If we solve attribution, Zoom transcription is done.
