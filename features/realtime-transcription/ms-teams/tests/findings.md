# MS Teams Realtime Transcription Findings

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 95 |
|-------|-------|----------|-------------|-------------|
| Create Teams meeting | 90 | Automated via CDP: Meet sidebar -> Create a meeting link -> fill name -> Create and copy link. Meeting 9383926870133 created and organizer joined | 2026-03-17 10:48 | Test with different meeting types (scheduled, channel) |
| Bot joins Teams mock | 85 | Bot navigates pre-join (Continue, name input, audio options, Join now), enters meeting, detects hangup button as admission indicator. Meeting IDs 8799, 8800 | 2026-03-17 10:33 | Test against real Teams meeting |
| Bot joins real meeting | 90 | Bot 8803 joined real meeting 9383926870133. Full flow: navigated URL, clicked Continue, set name "VexaBot-f5ff91", clicked Join now, entered lobby, was admitted by organizer via CDP, detected hangup-button as admission indicator, sent active callback. Failed at audio stage (all tracks muted — no active speaker) | 2026-03-17 10:49 | Test with active mic/speaker producing unmuted audio tracks |
| Admission detection | 90 | Real meeting: bot entered lobby, organizer's CDP page showed "Waiting in the lobby - VexaBot-f5ff91 (Guest)" with Admit/Deny buttons. Bot detected admission via hangup-button after organizer clicked Admit. Full automated lobby->admit->active flow confirmed | 2026-03-17 10:49 | Test with multiple bots in lobby simultaneously |
| Audio capture (mixed stream) | 60 | Mock: 85 (findMediaElements found active element). Real: bot found 5 media elements with srcObject+audioTracks=1 each, but all tracks had muted=true. No active speaker -> no unmuted tracks -> bot exited after 10 retries. Real Teams mutes tracks when nobody speaks | 2026-03-17 10:50 | Needs active mic producing speech. Bot should handle initially-muted tracks that unmute when someone speaks |
| Speaker detection (voice-level) | 85 | All 3 mock speakers detected via `[data-tid="voice-level-stream-outline"]` + `vdi-frame-occlusion` class. SPEAKER_START/END events fire correctly per speaking schedule. Scanned 9 elements, observed 3 with signal | 2026-03-17 10:33 | Test with real Teams participant tiles |
| Audio routed per speaker | 85 | `__vexaTeamsAudioData` callback received audio for all 3 speakers: "Bob Smith", "Alice Johnson", "Carol Williams". Per-speaker streams created: `teams-Bob_Smith`, `teams-Alice_Johnson`, `teams-Carol_Williams` | 2026-03-17 10:33 | Test with real audio and overlapping speakers |
| Audio reaches TX service | 85 | TranscriptionClient returns non-empty text. Language detected as `en`. Draft and confirmed segments generated: e.g. "This report shows we are 20% over budget on compute resources." and Russian text | 2026-03-17 10:33 | Test with real speech audio |
| WS delivery | 90 | Connected ws://localhost:8056/ws with x-api-key header, subscribed to {platform:"teams", native_id:"9383926870133"}. Received: subscribed confirmation, meeting.status:awaiting_admission (T+14s), meeting.status:active (T+34s), meeting.status:failed (T+69s). Full event stream verified | 2026-03-17 10:49 | Test with transcription segments flowing through WS |
| REST /transcripts | 85 | Mock: `GET /transcripts/teams/9381841545598` returned 8 segments with 3 unique speakers. Real: `GET /transcripts/teams/9383926870133` returned meeting data with status=failed, 0 segments (expected — no audio captured) | 2026-03-17 10:50 | Test with real meeting producing segments |

**Overall: 82/100** — Real meeting join+admission+WS fully automated. Bottleneck: audio capture requires active speaker (muted tracks in silent meeting).

**Gate: FAIL** — Audio capture at 60 (muted tracks in real meeting, needs active mic).

**Bottleneck:** Audio capture — bot's `findMediaElements` requires `track.enabled && !track.muted`, but Teams starts all tracks muted when nobody speaks. The bot exits after 10 retries (~30s). Need either: (a) active mic producing speech, or (b) bot code to accept muted tracks and listen for unmute events via `track.onunmute`.

**To reach 95:** Test with active mic/speakers. Fix bot to handle initially-muted audio tracks. Run full pipeline: speech -> audio capture -> transcription -> WS + REST delivery.

## Real meeting test (2026-03-17 10:48)

**Meeting:** 9383926870133 (Vexa Bot E2E Test)
**URL:** `https://teams.live.com/meet/9383926870133?p=3M0pEks0lEe8EiJqWi`
**Bot ID:** 8803

### Automated flow (all via CDP):
1. Connected to browser-1 (CDP 9222, Teams session Speaker D)
2. Navigated to Meet sidebar -> clicked "Create a meeting link"
3. Filled title "Vexa Bot E2E Test" -> clicked "Create and copy link"
4. Navigated to meeting URL -> clicked "Join now" as organizer
5. Bot launched via POST /bots API
6. Bot navigated to meeting, set name "VexaBot-f5ff91", clicked Join now
7. Organizer's page showed lobby notification: "VexaBot-f5ff91 (Guest) - Waiting in the lobby"
8. Clicked "Admit" button via CDP -> bot entered meeting
9. Bot detected admission via hangup-button
10. WS received: awaiting_admission -> active -> failed

### Bot behavior in real meeting:
- Found 5 media elements (all with srcObject, MediaStream, 1 audio track each)
- All 5 audio tracks: `enabled` status unclear, `muted=true`
- After 10 retries (30s), bot exited with `post_join_setup_error`
- Bot clicked hangup button and left cleanly

### WS events received:
```
[WS 10:49:08] subscribed
[WS 10:49:22] meeting.status: awaiting_admission
[WS 10:49:42] meeting.status: active
[WS 10:50:17] meeting.status: failed
```

## WS 403 investigation (2026-03-17 10:44)

**Root cause:** The previous "WS 403" was NOT an auth issue. The api-gateway's `/ws` endpoint accepts the connection first (`ws.accept()`), then authenticates. The actual issue was either:
1. Wrong payload format for subscribe (needs `{action:"subscribe", meetings:[{platform:"teams", native_id:"<13-digit>"}]}`)
2. Or the 403 was from a different layer (e.g., reverse proxy)

**Fix:** Use correct header (`x-api-key`) and correct subscribe payload format. WS connects and subscribes successfully.

## Mock fixes applied (2026-03-17)

1. **Removed audio element clone** — `audioContainer.appendChild(mixedAudioEl.cloneNode(false))` was causing `document.querySelector('audio')` to find the clone (no srcObject) before the real element, breaking per-speaker audio routing. Fixed by removing the clone.

2. **Added ARIA participants panel** — Added hidden `[role="menuitem"]` elements with `<img>` children matching `collectAriaParticipants()` expectations. Without this, the bot thought it was alone (participant count = 0) and would leave after 120s.

## Known architecture risks

1. **Mixed audio duplication** — all speakers mixed in one stream, routed by DOM detection. Detection lag -> wrong attribution.
2. **200ms debounce** — `MIN_STATE_CHANGE_MS` delays speaker state changes.
3. **No per-speaker isolation** — unlike Google Meet, no separate audio streams.
4. **vdi-frame-occlusion** — Teams-internal class, could change with updates.
5. **RTCPeerConnection hook** — complex, intercepts WebRTC. Fragile if Teams changes RTC setup.
6. **Mock uses AudioContext WAV playback** — real Teams uses RTCPeerConnection remote tracks. The mock's `MediaStreamAudioDestinationNode` is found directly by `findMediaElements`; real Teams would need the RTC hook to inject audio elements.
7. **Muted audio tracks** — Teams delivers audio via 5 media elements with initially-muted tracks. The bot's `findMediaElements` filter (`track.enabled && !track.muted`) rejects all elements when nobody is speaking. The bot needs to either accept muted tracks or wait for `track.onunmute` events.

## Learned (2026-03-17)

- Browser-1 (port 6080/9222) has the Teams session (Speaker D), NOT browser-2
- Playwright connectOverCDP may timeout on heavy sessions -- raw CDP fallback needed
- Guest join via link works without auth, needs organizer to admit from lobby
- Meeting link format: `https://teams.live.com/meet/<ID>?p=<PASSWORD>`
- Teams has no `teams.new` shortcut -- use Meet sidebar -> "Create a meeting link"
- Mock audio element must be the first `<audio>` in DOM order, or `setupPerSpeakerAudioRouting` fails
- Bot's `collectAriaParticipants()` needs `[role="menuitem"]` with `img`/`[role="img"]` children -- mock must provide this or bot thinks it's alone
- `native_meeting_id` for Teams must be 10-15 digit numeric or 16-char hex hash
- VAD (Silero) not available in bot container -- all audio sent to transcription (no silence filtering)
- Language detection works for both English and Russian speech in mock WAV files
- WS endpoint accepts first then authenticates -- no 403 on connect, errors come as JSON messages
- Subscribe payload: `{action:"subscribe", meetings:[{platform:"teams", native_id:"<ID>"}]}`
- Real Teams has 5 media elements with srcObject MediaStreams, each with 1 audio track — but all muted when no one speaks
- Bot lobby admission automated: organizer sees "Waiting in the lobby" popup with Admit/Deny buttons
- CDP-based Admit button click works reliably — `button:has-text("Admit")`
- Meeting coords encoded in URL as base64 JSON with meetingUrl, meetingCode, passcode
- Share link on Meet page triggers navigation — use the decoded URL from coords instead

## Test matrix for 95 certainty

| Scenario | Tested | Result |
|----------|--------|--------|
| Mock meeting (3 speakers, WAV audio) | Yes | PASS -- full pipeline end-to-end, 3 speakers, 8+ segments in REST API |
| Real meeting (automated create+join+bot+admit) | Yes | PARTIAL -- join+admission+WS work, audio failed (muted tracks) |
| Real meeting (2 participants, organizer+bot) | Yes | PARTIAL -- bot admitted, but no audio captured |
| Real meeting (3+ participants, with mic) | No | -- |
| Real meeting (guest join via link) | Yes (manual) | PASS (browser-2 joined as guest) |
| Real meeting (organizer admits from lobby) | Yes (automated) | PASS -- CDP clicked Admit, bot detected hangup-button |
| Real meeting (5+ participants) | No | -- |
| Real meeting (screen sharing active) | No | -- |
| Different meeting links | Yes | PASS -- 9381841545597, 9383926870133 both work |
| WS live transcription delivery | Yes | PASS -- subscribed, received meeting.status events (awaiting_admission, active, failed) |
| WS live transcript segments | No | BLOCKED -- bot failed before producing audio/segments |
| Personal meeting (`teams.live.com`) | Yes (mock) | PASS -- mock pipeline validated end-to-end |
| Enterprise meeting (`teams.microsoft.com`) | No | -- |
| Legacy deep link | No | -- |
| Government (`gov.teams.microsoft.us`) | No | -- |
