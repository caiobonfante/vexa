# Zoom Platform Support — Research Findings

**Researcher:** features researcher agent
**Date:** 2026-03-24
**Status:** Research complete, ready for implementation planning

---

## Executive Summary

Vexa already has **significant Zoom code** in the codebase — more than the "score 0" suggests. There are two complete implementation paths:

1. **Zoom Web (Playwright)** — fully implemented, compiled, and infrastructure-routed. PR #181 code is merged into `vexa-bot:dev`. ZOOM_WEB=true confirmed working in bot-manager. Needs real meeting testing only.
2. **Zoom Native SDK** — code exists with stub mode. Requires proprietary SDK binaries + Marketplace approval.

A third path exists externally:

3. **Zoom RTMS SDK** — new in 2025, no bot in meeting, receives raw audio via WebSocket. Requires Zoom Developer Pack (paid), account-level enablement.

**Recommendation: Zoom Web (Playwright) is the fastest path to score 60+.** It is already built and infrastructure-routed. The only gap is real meeting validation. RTMS is the strategic long-term path but has procurement and account-level blockers.

---

## Approach Comparison

| Dimension | Browser Web Client (Playwright) | Native Meeting SDK | RTMS SDK | Zoom Web SDK |
|-----------|-------------------------------|-------------------|----------|-------------|
| **Code exists in repo** | YES — complete: join, admission, recording, leave, removal, selectors | YES — with stub mode, native wrapper | NO | NO |
| **Infrastructure ready** | YES — ZOOM_WEB=true in compose, bot-manager routes correctly | Partial — SDK binaries not present | NO | NO |
| **Bot visible in meeting** | Yes (browser participant) | Yes (SDK participant) | NO — invisible, server-side | Yes (Web SDK participant) |
| **Audio capture** | PulseAudio (parecord from zoom_sink.monitor) | SDK raw audio API (per-participant PCM) | WebSocket stream (PCM 16-bit, configurable sample rate) | Limited — no raw audio access documented |
| **Speaker detection** | DOM polling (active speaker CSS class) | SDK onActiveSpeakerChange callback | Per-participant audio channels + transcript with speaker attribution | Unknown |
| **Marketplace review** | NOT required (browser guest join) | Required for external meetings | Required (General App + RTMS scopes) | Required |
| **OBF token** | NOT required (browser join, not SDK) | Required since March 2, 2026 for external meetings | Not applicable (webhook-based) | Required |
| **Zoom Developer Pack** | NOT required | NOT required | REQUIRED (paid, contact Zoom sales) | NOT required |
| **Account-level enablement** | NOT required | NOT required | REQUIRED (admin must enable RTMS) | NOT required |
| **Self-hostable** | YES | YES (if you have SDK binaries) | YES (your server receives streams) | YES |
| **Per-participant audio** | NO — mixed audio only (PulseAudio capture) | YES — SDK provides per-user raw audio | YES — per-participant channels available | NO |
| **Bidirectional (speak into meeting)** | YES — TTS via PulseAudio injection (same as Teams) | YES — SDK audio injection | NO — receive-only | YES |
| **Effort to reach score 30** | ~1 day (test with real meeting) | ~2 weeks (SDK binaries + build + Marketplace app) | ~3 weeks (Developer Pack procurement + webhook setup + SDK integration) | ~2 weeks (Web SDK integration, less documented) |
| **Effort to reach score 60** | ~3 days (real meeting join + transcription verified) | ~4 weeks (+ OBF flow + external meeting join) | ~4 weeks (+ audio pipeline integration) | Unknown |
| **CAPTCHA risk** | YES — Zoom may show CAPTCHA for guest joins | NO | NO | NO |
| **Selector fragility** | YES — Zoom web client DOM changes | NO | NO | YES (Web SDK DOM) |
| **Caption dependency** | Recording uses PulseAudio, not captions. Speaker detection uses DOM active-speaker indicator | NO | NO — gets raw transcript via API | N/A |

---

## Approach 1: Browser Web Client (Playwright) — RECOMMENDED FOR MVP

### Current State (already implemented)

All code exists at `services/vexa-bot/core/src/platforms/zoom/web/`:

| File | Purpose | Lines | Status |
|------|---------|-------|--------|
| `join.ts` | Navigate to `app.zoom.us/wc/{id}/join`, handle name input, permission dialogs, join button | 162 | Complete |
| `admission.ts` | Detect waiting room, poll for admission, handle rejection | 118 | Complete |
| `prepare.ts` | Post-admission: join computer audio, dismiss popups (AI Companion, tooltips) | 75 | Complete |
| `recording.ts` | PulseAudio capture (parecord) -> WhisperLive -> speaker polling via DOM | 360 | Complete |
| `leave.ts` | Click leave button, confirm dialog, stop recording | 74 | Complete |
| `removal.ts` | Detect host removal, meeting end, page navigation | 123 | Complete |
| `selectors.ts` | All DOM selectors — verified from live DOM inspection | 104 | Complete |
| `index.ts` | Platform strategy exports, wired into shared `runMeetingFlow` | 29 | Complete |

### Infrastructure routing (already working)

```
docker-compose.yml: ZOOM_WEB=true (in bot-manager env)
bot-manager: detects ZOOM_WEB=true, passes to container, logs "using Playwright web client"
vexa-bot: process.env.ZOOM_WEB === 'true' routes to handleZoomWeb() instead of native SDK
entrypoint.sh: Xvfb + PulseAudio + zoom_sink already configured
```

API acceptance test PASSED — `POST /bots` with `platform: "zoom"` creates container without SDK errors.

### Audio architecture

Unlike Google Meet (ScriptProcessorNode per participant) and Teams (captions + browser audio), Zoom Web uses:

1. **PulseAudio capture**: `parecord --raw --format=s16le --rate=16000 --channels=1 --device=zoom_sink.monitor`
2. Audio is **mixed** (all participants combined) — no per-speaker audio separation
3. PCM data sent to WhisperLive via WebSocket for transcription
4. **Speaker detection**: DOM polling every 250ms checks `.speaker-active-container__video-frame` for active speaker CSS class, sends SPEAKER_START/SPEAKER_END events to WhisperLive

This means speaker attribution depends on:
- WhisperLive receiving correct speaker events timed to audio
- Active speaker DOM element correctly reflecting who is talking
- Overlapping speech will attribute to the visually "active" speaker (same limitation as a single-track recording)

### What needs testing

1. **Real Zoom meeting join** — navigate to `app.zoom.us/wc/{id}/join`, name input, join
2. **CAPTCHA handling** — Zoom may show CAPTCHA for guest web client joins. This is the biggest risk. Evidence from Zoom developer forums suggests CAPTCHA appears for unsigned-in guests. Mitigation: the bot already dismisses permission dialogs, but CAPTCHA solving would require additional tooling (e.g., 2captcha service) or may be avoidable if meeting settings allow guest access.
3. **Waiting room** — admission.ts handles this, needs live validation
4. **Audio capture** — verify PulseAudio captures Zoom web client audio (zoom_sink routing)
5. **Speaker detection** — verify DOM active speaker indicator works in real meetings
6. **Transcription quality** — mixed audio -> WhisperLive quality with speaker attribution

### Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| CAPTCHA on guest join | HIGH | Test with different meeting settings. If CAPTCHA persists, fall back to RTMS or signed-in join |
| Zoom blocks headless Chromium | MEDIUM | Already using Playwright with puppeteer-extra stealth plugin. Zoom web client appears more permissive than expected (other tools like zoomrec work) |
| Selector drift | MEDIUM | Selectors were verified from live DOM. Monitor for changes. Use fallback selectors where possible |
| Mixed audio limits speaker attribution | MEDIUM | Active speaker DOM polling provides attribution. Not as precise as per-participant audio but functional |
| "Join from browser" disabled by meeting admin | LOW | Most meetings allow browser join. Cannot mitigate — meeting host choice |

### Estimated effort

| Milestone | Effort | Outcome |
|-----------|--------|---------|
| Real meeting test (score 30) | 0.5-1 day | Bot navigates, enters name, joins meeting |
| Audio capture verified (score 50) | 1 day | PulseAudio captures audio, WhisperLive receives it |
| Transcription E2E (score 60) | 1-2 days | Segments appear in Redis/Postgres with speaker names |
| Multiple meetings (score 80) | 2-3 days | Different meeting IDs, regional subdomains, waiting room |
| Production-grade (score 90) | 1 week | Edge cases, error recovery, CAPTCHA handling if needed |

---

## Approach 2: Native Meeting SDK

### Current State

Code exists at `services/vexa-bot/core/src/platforms/zoom/`:
- `sdk-manager.ts` — SDK lifecycle, JWT auth, join, raw audio
- `strategies/join.ts` — SDK init, authenticate, join meeting, join VoIP audio
- `strategies/recording.ts` — SDK raw audio capture via PulseAudio
- Native C++ wrapper at `native/zoom_meeting_sdk/` — headers present, binary NOT present

### Blockers

1. **SDK binaries not in repo** — proprietary, must be downloaded from Zoom
2. **Marketplace review required** — 4-6 weeks for approval to join external meetings
3. **OBF token enforcement** (March 2, 2026) — bot joining external meetings needs OBF token, requiring:
   - User completes Zoom OAuth in dashboard
   - bot-manager mints OBF token via `GET /v2/users/me/token?type=onbehalf`
   - Authorizing user must be **present in the meeting** while bot is active
4. **Linux x86_64 only** — SDK is platform-specific

### When to use

- When per-participant raw audio is critical (e.g., speaker diarization quality requirements exceed what DOM-based attribution provides)
- When bidirectional audio (TTS into meeting) is needed AND RTMS is not available
- For production deployments with approved Marketplace app

### Estimated effort

| Milestone | Effort |
|-----------|--------|
| SDK download + build + init | 2-3 days |
| Marketplace app creation | 1 day |
| OBF flow testing | 2-3 days |
| Marketplace review | 4-8 weeks (blocking) |
| External meeting join | After approval |

---

## Approach 3: Zoom RTMS SDK — STRATEGIC LONG-TERM

### What RTMS is

RTMS (Real-Time Media Streams) is a **server-side data pipeline** that gives your app access to live audio, video, transcript data, and participant events from Zoom Meetings via WebSocket. No bot appears in the meeting.

### How it works

```
1. Zoom meeting starts
2. Zoom sends `meeting.rtms_started` webhook to your server
3. Your server creates an RTMS Client instance
4. Client connects via signaling WebSocket (HMAC-SHA256 auth)
5. Media WebSocket streams raw audio, video, transcripts
6. Per-participant audio channels available
7. Meeting ends -> streams stop
```

### SDK availability

- NPM package: `@zoom/rtms` (Node.js >= 20.3.0)
- Python: `zoom-rtms` (Python 3.10+)
- Go: planned
- GitHub: https://github.com/zoom/rtms

### Audio specifications

| Parameter | Options |
|-----------|---------|
| Format | PCM 16-bit raw |
| Sample rate | 8kHz, 16kHz, 32kHz, 48kHz |
| Channels | Mono, Stereo |
| Data option | Mixed stream OR per-participant |
| Frame duration | 20ms default |
| Codec | RAW_AUDIO, OPUS |

### Transcript data

RTMS provides live transcripts with speaker attribution in UTF-8, supporting 37 languages. This eliminates the need for Whisper entirely for Zoom meetings.

### Prerequisites (blockers)

| Prerequisite | Status | Timeline |
|-------------|--------|----------|
| Zoom Developer Pack | NOT purchased | Contact Zoom sales, pricing unknown |
| Account-level RTMS enablement | NOT enabled | Admin setting after Developer Pack |
| General App in Marketplace | NOT created | 1 day to create |
| RTMS scopes configured | NOT configured | Part of app creation |
| Webhook endpoint for `meeting.rtms_started` | NOT built | 1-2 days to build |
| Users on Zoom client 6.5.5+ | Not controllable | User dependency |
| Host must approve RTMS sharing | Not controllable | UX friction for users |

### Critical limitations

1. **Receive-only** — cannot send audio/chat back into meeting (no speaking bot support)
2. **Host dependency** — if original host leaves and replacement has sharing disabled, stream interrupts
3. **No resume** — disconnected sessions cannot resume; data lost permanently
4. **No breakout rooms** — not supported
5. **Host approval required** — adds UX friction (host must approve real-time sharing)
6. **Paid feature** — requires Zoom Developer Pack with unknown pricing

### Integration architecture (if pursued)

```
New service: zoom-rtms-bridge
  - Express server on port 8080 (webhook receiver)
  - Listens for meeting.rtms_started webhook
  - Creates RTMS Client per meeting
  - Pipes audio to existing WhisperLive OR uses RTMS transcripts directly
  - Publishes segments to Redis (same as existing pipeline)
  - No browser, no bot container, no PulseAudio

Changes needed:
  - bot-manager: new "rtms" mode alongside "browser" and "sdk"
  - api-gateway: webhook endpoint for Zoom
  - New service: zoom-rtms-bridge (Node.js)
  - User flow: Zoom OAuth + RTMS consent
```

### Estimated effort (assuming Developer Pack available)

| Milestone | Effort |
|-----------|--------|
| Webhook endpoint + RTMS client | 2-3 days |
| Audio pipeline integration | 2-3 days |
| Transcript pipeline (bypass Whisper) | 1-2 days |
| Testing with real meetings | 2-3 days |
| Total | ~2 weeks (engineering) + procurement time |

---

## Approach 4: Zoom Web SDK — NOT RECOMMENDED

The Zoom Web SDK (`@zoom/meetingsdk`) is designed for embedding Zoom into web applications. It:
- Requires OAuth/JWT authentication
- Requires Marketplace review
- Has limited raw audio access (the `mediaCapture` API triggers recording consent but doesn't provide raw streams)
- Is intended for building Zoom-embedded UIs, not bots

Per Recall.ai's research: "the mediaCapture API call only triggers a recording consent popup but doesn't actually give access to audio and video streams."

Not recommended — more complexity than browser automation with worse audio access.

---

## How Competitors Handle Zoom

| Competitor | Primary Approach | Details |
|-----------|-----------------|---------|
| **Recall.ai** | Meeting bot (browser) + RTMS | Bot joins as participant; also offers "Meeting Direct Connect" via RTMS (no bot in meeting). RTMS requires user OAuth. |
| **MeetingBaaS** | Browser bot (Playwright) | Open-source (BSL) browser automation. Joins via web client, scrapes captions. Same architecture as Vexa's existing code. |
| **Otter.ai** | Proprietary bot | OtterPilot joins as named participant. Likely Meeting SDK. |
| **Fireflies** | Bot participant | Joins as "Fireflies.ai Notetaker". Likely Meeting SDK with Marketplace approval. |
| **tl;dv** | Bot participant | Joins as participant. Browser-based approach documented. |
| **zoomrec** | VNC + Python | Open-source. Uses VNC/Xfce container, Python automation, FFmpeg for recording. Simpler but no live transcription. |

**Key insight**: Browser automation (Playwright joining web client) is the **industry-standard approach** for meeting bots that need to work quickly without Marketplace approval. MeetingBaaS, Recall.ai (for their bot path), and multiple open-source tools all use this approach.

---

## Recommended Implementation Plan

### Phase 1: Browser Web Client MVP (Target: score 60, effort: 3-5 days)

**The code is already built. This is a testing and validation phase, not a coding phase.**

1. Create a real Zoom meeting (free account works)
2. Run `POST /bots` with the Zoom meeting URL
3. Verify: bot container starts, navigates to `app.zoom.us/wc/{id}/join`
4. Verify: name entered, join clicked, admitted to meeting
5. Verify: PulseAudio captures audio from Zoom web client
6. Verify: WhisperLive receives audio, produces transcription
7. Verify: speaker attribution via DOM active speaker indicator
8. Verify: segments appear in Redis and via REST API
9. Test: waiting room, host removal, meeting end
10. Test: regional subdomain URLs (`us05web.zoom.us/j/...`)

If CAPTCHA blocks step 4, investigate:
- Meeting setting "Require CAPTCHA when participants join" (host can disable)
- Signed-in browser session (cookie persistence)
- CAPTCHA solving service integration

### Phase 2: Hardening (Target: score 80, effort: 1 week)

1. Handle edge cases: meeting not started, invalid meeting ID, expired link
2. Test with 2+ speakers, verify speaker switching detection
3. Test TTS-bot-driven scenarios (controlled ground truth)
4. Add Zoom to mock meeting suite for automated testing
5. Regression test: Teams and GMeet still work after changes

### Phase 3: RTMS Evaluation (parallel, effort: 2-3 days research)

1. Contact Zoom about Developer Pack pricing
2. Create proof-of-concept with RTMS quickstart
3. Evaluate whether RTMS transcripts are sufficient (skip Whisper)
4. Decision point: if RTMS is affordable and works, plan migration from browser to RTMS for Zoom

### Phase 4: Production (Target: score 90+)

- Whichever approach wins (browser or RTMS), harden for production
- Add to CI/CD testing matrix
- Document Zoom-specific configuration in `docs/platforms/zoom.md`
- Dashboard: ensure Zoom OAuth flow works for users who need OBF (native SDK path only)

---

## Code Locations That Need Changes

### Already complete (no changes needed for MVP)

| File | Purpose |
|------|---------|
| `services/vexa-bot/core/src/platforms/zoom/web/*` | All 8 modules (join, admission, prepare, recording, leave, removal, selectors, index) |
| `services/vexa-bot/core/src/platforms/zoom/index.ts` | Routes to web path when `ZOOM_WEB=true` |
| `services/vexa-bot/core/entrypoint.sh` | Xvfb, PulseAudio, zoom_sink already configured |
| `services/bot-manager/app/orchestrator_utils.py` | Detects `ZOOM_WEB=true`, passes to container |
| `features/agentic-runtime/deploy/docker-compose.yml` | `ZOOM_WEB=true` in bot-manager env |

### May need changes (based on testing)

| File | Potential Change |
|------|-----------------|
| `services/vexa-bot/core/src/platforms/zoom/web/selectors.ts` | Selector updates if Zoom DOM changed |
| `services/vexa-bot/core/src/platforms/zoom/web/join.ts` | CAPTCHA handling if encountered |
| `services/vexa-bot/core/src/platforms/zoom/web/recording.ts` | Speaker detection tuning based on real meeting behavior |
| `services/bot-manager/app/orchestrator_utils.py` | Zoom-specific container config (memory, timeout) if needed |

### For RTMS path (future)

| Component | Changes |
|-----------|---------|
| New service: `zoom-rtms-bridge` | Webhook receiver + RTMS client + audio pipeline |
| `services/bot-manager/app/main.py` | New "rtms" mode for Zoom bots |
| `services/api-gateway` | Webhook endpoint for Zoom `meeting.rtms_started` |
| Dashboard OAuth | Additional RTMS scopes in Zoom app configuration |

---

## Prerequisites

### For Browser Web Client (Phase 1)

- [x] ZOOM_WEB=true in docker-compose.yml
- [x] Bot-manager routes Zoom to web path
- [x] vexa-bot:dev image has compiled zoom/web/ modules
- [x] PulseAudio + zoom_sink configured in entrypoint.sh
- [ ] Real Zoom meeting URL for testing
- [ ] Verify CAPTCHA behavior on guest web client join

### For RTMS (Phase 3+)

- [ ] Zoom Developer Pack (paid, pricing unknown)
- [ ] Account-level RTMS enablement
- [ ] General App with RTMS scopes in Marketplace
- [ ] Webhook endpoint deployed and accessible from Zoom
- [ ] Users on Zoom client 6.5.5+

### For Native SDK (not recommended for MVP)

- [ ] Zoom Meeting SDK Linux x86_64 binaries
- [ ] Marketplace app submission and review (4-8 weeks)
- [ ] OBF token flow (user must be present in meeting)

---

## Key External References

- [Zoom RTMS Documentation](https://developers.zoom.us/docs/rtms/)
- [RTMS Quickstart JS](https://github.com/zoom/rtms-quickstart-js)
- [@zoom/rtms npm package](https://www.npmjs.com/package/@zoom/rtms)
- [Recall.ai: How to Build a Zoom Bot](https://www.recall.ai/blog/how-to-build-a-zoom-bot)
- [Recall.ai: What is Zoom RTMS?](https://www.recall.ai/blog/what-is-zoom-rtms)
- [Recall.ai: Meeting Direct Connect for RTMS](https://docs.recall.ai/docs/meeting-direct-connect-for-zoom-rtms)
- [MeetingBaaS: Zoom OBF Token Changes](https://www.meetingbaas.com/en/blog/zoom-obf-token-changes)
- [Zoom OBF Transition FAQ](https://developers.zoom.us/docs/meeting-sdk/obf-faq/)
- [Zoom Developer Forum: RTMS vs Linux SDK Pricing](https://devforum.zoom.us/t/pricing-feasibility-validation-rtms-vs-linux-sdk-for-external-meeting-capture/141332)
- [zoomrec (open-source headless Zoom recorder)](https://github.com/kastldratza/zoomrec)
- [MeetingBaaS open-source bot](https://github.com/Meeting-BaaS/meeting-bot-as-a-service)

---

## Dead Ends and Warnings

| Finding | Source | Implication |
|---------|--------|-------------|
| OBF token required for SDK bots joining external meetings since March 2, 2026 | Zoom developer blog | Native SDK path requires user OAuth + presence in meeting |
| CAPTCHA on web client guest join is an account-level setting | Zoom developer forum | Some meetings will block browser bot join. No universal workaround. |
| Zoom Web SDK `mediaCapture` doesn't provide raw audio streams | Recall.ai research | Web SDK is not viable for audio capture |
| RTMS is receive-only — no bidirectional audio | Zoom docs | RTMS cannot support speaking bot use case |
| RTMS host must approve sharing, stream breaks if host leaves | Zoom docs | UX friction, reliability concern |
| Zoom Developer Pack pricing is not public | Zoom sales requirement | Budget unknown until sales contact |
| Marketplace review takes 4-8 weeks | Multiple sources | Any SDK approach has significant lead time |
