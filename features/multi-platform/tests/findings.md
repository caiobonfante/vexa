# Multi-Platform Test Findings

## Certainty Ladders

### Google Meet

| Level | Gate | Score | Evidence | Last checked |
|-------|------|-------|----------|-------------|
| 60 | Mock passes (full-messy, 3 speakers) | 90 | 7 segments, all speakers, Russian included | 2026-03-16 |
| 70 | Mock passes (rapid-overlap) | 0 | Scenario created, not tested | — |
| 75 | Real meeting: standard URL (abc-defg-hij) | 95 | 3 real meetings tested (cxi-ebnp-ixk, hcx-qgnx-dre, kpw-ccvz-umz) | 2026-03-17 |
| 80 | Real meeting: waiting room + host admits via CDP | 0 | Auto-admitted on all tests (same-account). Need external bot join | — |
| 85 | Real meeting: 3+ participants with active mics | 0 | Host had no mic in all tests | — |
| 88 | Real meeting: custom Workspace nickname URL | 0 | Not tested | — |
| 90 | Real meeting: participant joins mid-meeting | 0 | Not tested | — |
| 92 | Real meeting: participant leaves mid-meeting | 0 | Not tested | — |
| 94 | Real meeting: screen sharing active | 0 | Not tested | — |
| 95 | 5 different meeting URLs, all pass | 60 | 3/5 URLs tested | 2026-03-17 |
| 97 | 10+ meetings, varying participant counts | 0 | Not tested | — |
| 99 | All above + rapid speech + multilingual + noise | 0 | Not tested | — |

**Current: 75 (real meeting with standard URL passes, but no admission/mic/dynamic tests)**

### MS Teams

| Level | Gate | Score | Evidence | Last checked |
|-------|------|-------|----------|-------------|
| 60 | Mock passes (full-messy, 3 speakers) | 85 | 8 segments, 3 speakers, English+Russian | 2026-03-17 |
| 70 | Mock passes (rapid-overlap) with ring buffer | 0 | Ring buffer being implemented | — |
| 75 | Real meeting: personal URL (teams.live.com) | 90 | Meeting 40: teams.live.com/meet/93962005085349, bot joined + transcribed. 11 segments, 2 speakers correct. | 2026-03-24 |
| 78 | Real meeting: bot admitted from lobby via CDP | 90 | Meeting 40: auto-admit admitted 3 bots (recorder + 2 speakers) via CDP lobby click | 2026-03-24 |
| 80 | Real meeting: audio captured (muted tracks accepted) | 90 | Meeting 40: 11 segments with correct text, max 31s. Audio capture working with rebuilt vexa-bot:dev. | 2026-03-24 |
| 83 | Real meeting: enterprise URL (teams.microsoft.com) | 0 | Not tested | — |
| 85 | Real meeting: 3+ participants with mics | 90 | Meeting 40: 14 segments, 3 speakers (Alice, Bob, Charlie) all correctly attributed. Alpha + Beta verified. | 2026-03-24 |
| 88 | Real meeting: legacy deep link URL | 0 | Not tested | — |
| 90 | Real meeting: ring buffer captures first-second speech | 0 | Ring buffer being implemented | — |
| 92 | Real meeting: participant joins/leaves | 0 | Not tested | — |
| 94 | Real meeting: screen share active | 0 | Not tested | — |
| 95 | 5 different meeting links, personal + enterprise | 0 | Only 1 link tested | — |
| 97 | Government URL (gov.teams.microsoft.us) | 0 | No access to gov tenant | — |
| 99 | All above + rapid speech + multilingual | 0 | Not tested | — |

**Current: 85 (real meeting PASS: personal URL, lobby admission, audio capture, 3-speaker attribution all validated in meeting 40, 2026-03-24)**

### Zoom

| Level | Gate | Score | Evidence | Last checked |
|-------|------|-------|----------|-------------|
| 0 | Code exists + infrastructure routed | 90 | 8 complete modules at platforms/zoom/web/. ZOOM_WEB=true confirmed in meeting-api. POST /bots with platform=zoom creates container. No SDK needed. | 2026-03-24 |
| 30 | Bot navigates to Zoom web client, enters name | 90 | Meeting 57: navigated to app.zoom.us/wc/87932820681/join, entered name "Vexa Zoom Test", muted mic/video, clicked Join. No CAPTCHA. | 2026-03-25 |
| 50 | Bot joins real Zoom meeting, audio captured via PulseAudio | 90 | Meeting 57: bot immediately admitted (no waiting room). PulseAudio capture started with 3 streams. Speaker "Dmtiry Grankin" detected via DOM polling. Recording to WAV started. Chat panel opened. | 2026-03-25 |
| 60 | Transcription works end-to-end | 90 | Meeting 63: 11 confirmed segments, Russian speech transcribed correctly. WhisperLive connected, PulseAudio capture working. CUDA OOM resolved (workers restarted). | 2026-03-25 |
| 70 | Waiting room + host admission | 0 | Not tested (meetings 57/63 had no waiting room — bot was immediately admitted). admission.ts ready but unvalidated. | — |
| 80 | Transcription works with 2+ speakers, correct attribution | 50 | Meeting 72: Speaker "Dmtiry Grankin" detected via DOM polling (amplitude-gated fix works). TTS bot survived >10s (grace period fix works). But WhisperLive stubbed — no segments in DB. Transcription service healthy but per-speaker pipeline not connecting. | 2026-03-25 |
| 90 | Multiple meetings, different IDs | 0 | Not tested | — |
| 95 | Regional subdomain URLs (us05web.zoom.us/j/...) | 90 | Meeting 57 used `us05web.zoom.us` regional subdomain — URL correctly routed via `meeting_url` field. | 2026-03-25 |

**Current: 60 (transcription works end-to-end. Speaker detection fixed (amplitude-gated voting), TTS bots survive (grace period). WhisperLive stubbed in per-speaker pipeline — blocks transcription segments.)**

#### Zoom first live test (2026-03-25)

**Meeting 57** — real Zoom meeting at `us05web.zoom.us/j/87932820681`

| Step | Result |
|------|--------|
| API accepts request | PASS — meeting 57 created, container `vexa-bot-57-b371a184` spawned |
| ZOOM_WEB routing | PASS — meeting-api logs "using Playwright web client for Zoom" |
| CAPTCHA | **NO CAPTCHA** — bot navigated directly to pre-join page |
| Name + mute + join | PASS — name entered, mic/video muted, Join clicked |
| Admission | PASS — immediately admitted (Leave button visible) |
| Popup dismissal | PASS — dismissed "feature tip" + "chatting as guest" popups |
| Status transitions | PASS — `requested → joining → active` |
| PulseAudio capture | PASS — 3 audio streams, capture receiving data |
| Speaker detection | PASS — DOM polling detected "Dmtiry Grankin" via active speaker CSS |
| Recording | PASS — WAV recording started |
| Chat panel | PASS — opened and observing |
| Transcription | FAIL — external CUDA OOM (not Zoom code) |

**Two code gaps found:**
1. `speaker-identity.ts:332` — `resolveSpeakerName()` only handles `googlemeet` and `msteams`, returns empty for `zoom`. Per-speaker audio track naming doesn't work for Zoom. Low priority — DOM polling speaker detection works as primary path.
2. `WHISPER_LIVE_URL` empty in bot container — WhisperLive runs in stub mode. Per-speaker transcription client uses direct HTTP to transcription service (which was OOM).

#### Zoom second live test (2026-03-25)

**Meeting 63** — real Zoom meeting at `us04web.zoom.us/j/78705332776`

| Step | Result |
|------|--------|
| API accepts request | PASS — meeting 63 created, container spawned |
| Bot joins | PASS — immediately admitted, status → active |
| Transcription | PASS — 11 confirmed segments, Russian speech correctly transcribed |
| Speaker detection | PASS — DOM polling detected "Dmitriy Grankin" via CSS selector |
| Speaker attribution | FAIL — resolveSpeakerName() returns "" for zoom, segments have empty speaker |
| TTS speak command | PARTIAL — TTS synthesizes audio but `[Microphone] Unsupported platform for mic toggle: zoom` |
| TTS audio in meeting | FAIL — audio plays to PulseAudio but doesn't reach meeting (virtual_mic not routed to browser) |
| Speaker bots join | FAIL — bots 66/67/69 (Alice/Bob/Charlie) went active→completed in ~4s (ejected) |
| Multi-speaker data | BLOCKED — no TTS speakers could stay in meeting |

**Three blockers found and FIXED (2026-03-25):**
1. ~~`microphone.ts` — mic toggle not implemented for zoom~~ **FIXED** — `toggleZoomMic()` implemented, clicks `.join-audio-container__btn`. Verified by independent verifier.
2. ~~Speaker bots ejected ~4s after joining~~ **FIXED** — `removal.ts` false-positive on `framenavigated` during Zoom audio init handshake. Added 10s grace period. Verified by independent verifier.
3. ~~`speaker-identity.ts:332` — resolveSpeakerName() returns empty for zoom~~ **FIXED** — Added `trackLastAudioMs` amplitude tracking. Active speaker name now votes only on the most recently active audio track, preventing `isNameTaken` from blocking all tracks. Verified by independent verifier, compile clean.

#### Zoom research findings (2026-03-24)

- **Zoom Web code discovered:** 8 complete Playwright modules at `services/vexa-bot/core/src/platforms/zoom/web/`. All compiled and present in vexa-bot:dev image.
- **Infrastructure routed:** `ZOOM_WEB=true` confirmed in meeting-api env.
- **CAPTCHA risk mitigated:** First live test showed no CAPTCHA on guest web join. May vary by meeting settings.
- **Three approaches evaluated** (full details in `zoom-research.md`): Browser Web Client (validated, working), Native Meeting SDK (requires proprietary binaries + Marketplace review), Zoom RTMS SDK (strategic long-term, requires paid Developer Pack).
- **Competitor validation:** Browser automation is the industry standard. Recall.ai, MeetingBaaS, and multiple open-source tools use the same approach.

### Cross-Platform

| Level | Gate | Score | Evidence | Last checked |
|-------|------|-------|----------|-------------|
| 60 | Same POST /bots API works for Google Meet + Teams | 90 | Both platforms create bots via same endpoint | 2026-03-17 |
| 80 | Same transcript format from both platforms | 85 | Both return {speaker, text, start_time, end_time, language} | 2026-03-17 |
| 90 | Same WS delivery format from both platforms | 0 | WS verified for Google Meet only | — |
| 95 | Switching between platforms in same session | 0 | Not tested | — |

**Current: 60 (API shape matches, WS only verified for Google Meet)**

## Overall Multi-Platform Score

```
Google Meet:   75/100
MS Teams:      85/100  (was 65 — audio capture + 3-speaker validated 2026-03-24)
Zoom:          60/100  (was 50 — transcription validated 2026-03-25)
Cross-platform: 60/100
────────────────────
Weighted avg:  74/100  (Google 40%, Teams 40%, Zoom 10%, Cross 10%)
```

## Out of scope

- Domain-restricted Google Meet (org-only) — bot rejected as unauthenticated guest
- Org-only Teams — bot rejected as anonymous guest
- Authenticated Zoom — requires user account
- Zoom Events — unique per-registrant links, not joinable
- Teams Live Events / Webinars — different URL format, untested
