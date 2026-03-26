# Zoom Web Client Audio Join Flow Research

Date: 2026-03-25
Context: Task #1 — Recorder bot enters meetings without audio. Research the exact audio join flow.

## Executive Summary

**Root cause confirmed:** Clicking "Continue without microphone and camera" prevents the bot from BOTH sending AND receiving audio. The bot enters the meeting visually but is completely deaf — no audio infrastructure is initialized. The `prepareZoomWebMeeting()` post-admission "Join Audio" retry is the correct fix path but needs robust selectors and timing.

**Critical insight from Zoom architecture:** Zoom's audio receive path (WebSocket/DataChannel -> WASM Decoder -> AudioWorklet -> WebAudio destination) does NOT technically require getUserMedia. However, Zoom's UI gates ALL audio (send + receive) behind the "Join Audio" button. You must click "Join Audio" to hear anything, even though the underlying tech could work without mic permission.

## Question 1: Does "Continue without microphone and camera" prevent RECEIVING audio?

**YES — it prevents both sending AND receiving.**

Evidence:
- Zoom Developer Forum (SDK v3.1.6): "If the user does not click the 'Join Audio' button and closes the popup, they are unable to speak or hear other participants." ([source](https://devforum.zoom.us/t/auto-enable-speaker-audio-without-clicking-join-audio-button-in-meeting-sdk/114650))
- Zoom Developer Forum (SDK v2.8.0-2.9.7): "Nothing happens and user gets left out of audio and can't join back into the audio without refreshing the page." ([source](https://devforum.zoom.us/t/join-audio-leave-computer-audio-buttons-dont-work-reliably/81658))
- Feature-log.md confirms: bot 60 found 3 media elements but `maxVal` never exceeded 0.005 threshold — elements exist in DOM but carry no audio data because audio channel was never joined.

**This is the #1 blocker.** The current code (join.ts:107) clicks "Continue without microphone and camera" for recorder bots, which skips audio entirely. The bot joins the meeting "visually" only.

## Question 2: Exact UI Flow for Joining Audio in Zoom Web Client

The Zoom web client audio join is a **two-step process**:

### Step 1: Pre-join permission dialog
When navigating to `app.zoom.us/wc/{id}/join`, Zoom shows a permission dialog:
- **Option A:** "Allow" — triggers `getUserMedia({audio: true})`, grants mic access
- **Option B:** "Continue without microphone and camera" — skips getUserMedia entirely

Current code clicks Option B for recorder bots (join.ts:107).

### Step 2: In-meeting audio join (post-admission)
After entering the meeting, if audio was not joined in Step 1, a **headphone icon** appears in the footer toolbar. The flow is:

1. **Footer button:** `button.join-audio-container__btn` (selector in selectors.ts) — shows headphone icon with "Join Audio" aria-label
2. **Click it** -> Opens audio dialog popup
3. **Dialog button:** "Join Audio by Computer" or "Join with Computer Audio" — this is the key button
4. **Click it** -> Zoom initializes the WebAudio pipeline, starts receiving audio

The `prepareZoomWebMeeting()` in prepare.ts already attempts this but has timing/reliability issues.

### Alternative: URL parameter `prefer=1`
Adding `prefer=1` to the web client URL auto-connects computer audio:
```
https://app.zoom.us/wc/{id}/join?pwd={pwd}&prefer=1
```
**Warning:** Known reliability issues reported in 2020 — audio sometimes fails to connect even though the dialog is skipped. Needs live testing to verify current behavior. ([source](https://devforum.zoom.us/t/zoom-web-client-fails-to-connect-audio-when-using-prefer-1/14037))

### Alternative: Programmatic `#pc-join` click
From Zoom Developer Forum, a workaround for the SDK:
```javascript
setTimeout(function() {
  document.querySelector("#pc-join").click();
}, 10000);
```
The ~10-second delay is critical — clicking earlier prevents audio from functioning. The `#pc-join` selector is from the SDK dialog, not confirmed for the native web client. Needs live DOM verification. ([source](https://devforum.zoom.us/t/web-sdk-connecting-the-user-with-computer-audio-automatically-when-joining/2682))

## Question 3: "Join Audio" Button After Joining Without Mic — Selectors

### Footer button (always present when audio not joined)
```
Selector: button.join-audio-container__btn
Aria-label: "Join Audio" (when not joined) / "Mute" or "Unmute" (when joined)
Location: Footer toolbar, leftmost position
```
Already defined in selectors.ts as `zoomAudioButtonSelector`.

### Audio dialog popup (after clicking footer button)
```
Button text: "Join Audio by Computer" OR "Join with Computer Audio"
Possible selectors (need live verification):
  - button:has-text("Join Audio by Computer")
  - button:has-text("Join with Computer Audio")
  - #pc-join (from SDK — may not exist in native web client)
  - .join-audio-by-computer (unverified)
```
Already handled in prepare.ts:50 with both text variants.

### Key timing detail
The audio button may not be immediately visible after admission. prepare.ts retries up to 5 times with 2s intervals — this should be sufficient but may need longer delays for slow connections.

## Question 4: Open-Source Zoom Bot Implementations

### screenappai/meeting-bot (TypeScript/Playwright)
- **Does NOT handle audio join explicitly.** Handles mic/camera notifications (dismiss close buttons) but never clicks "Join Audio" or "Join Audio by Computer"
- Uses injected MediaRecorder for recording, not ScriptProcessor
- No PulseAudio setup visible
- ([source](https://github.com/screenappai/meeting-bot))

### Recall.ai blog (Playwright/Puppeteer)
- Recommends fake media device flags: `--use-fake-device-for-media-stream`, `--use-fake-ui-for-media-stream`
- Does NOT capture audio — uses Zoom's built-in captions for transcription instead
- Acknowledges limitation: "Some organizations disable captions entirely"
- No audio join handling documented
- ([source](https://www.recall.ai/blog/how-to-build-a-zoom-bot))

### kastldratza/zoomrec (Python/FFmpeg)
- Uses PulseAudio (`paplay`) for audio routing
- Docker-based headless recording
- Different approach: records screen + system audio via FFmpeg, not per-speaker
- ([source](https://github.com/kastldratza/zoomrec))

**Key finding:** No open-source Zoom bot implementation handles the "Join Audio by Computer" flow correctly. This is a gap across the ecosystem. Most either use captions (Recall.ai) or screen recording (zoomrec). Our per-speaker ScriptProcessor approach is novel.

## Question 5: Zoom Developer Forum Discussions

### "Join Audio by Computer" button disabled (~15% of meetings)
- Reported in SDK v5.1.2, affects ~15% of meetings
- Button appears grayed out / disabled
- No reliable fix found — may require page refresh
- ([source](https://devforum.zoom.us/t/bug-meeting-sdk-web-v5-1-2-join-audio-by-computer-button-disabled-15-of-meetings/142317))

### Speaker sometimes doesn't work with Puppeteer + fake media
- Sporadic — most sessions work, some fail silently
- Root cause theory: browser autoplay policy blocks audio playback without user interaction
- Workaround: ensure user gesture (click) before audio plays
- ([source](https://devforum.zoom.us/t/the-speaker-sometimes-does-not-work-when-using-puppeteer-with-a-fake-media-device/132367/17))

### No official API for auto-joining audio
- Zoom staff confirmed: "the only way to set the audio option automatically is through your Zoom app settings"
- Web SDK has `ZoomMtg.showJoinAudioFunction({ show: false })` but this only HIDES the dialog without joining
- The `prefer=1` URL param and `#pc-join` click are community workarounds, not official
- ([source](https://devforum.zoom.us/t/web-sdk-connecting-the-user-with-computer-audio-automatically-when-joining/2682))

## Question 6: Zoom "Join with Computer Audio" Dialog Details

### What it looks like
After clicking the footer "Join Audio" button, a popup/modal appears with tabs:
- **Phone Call** tab — dial-in numbers
- **Computer Audio** tab — "Join Audio by Computer" button (blue, prominent)
- Possible "Call Me" tab

### What it does technically
Clicking "Join Audio by Computer":
1. Triggers `getUserMedia({audio: true})` — requests mic permission
2. Initializes Zoom's WebAssembly audio decoder/encoder pipeline
3. Starts the AudioWorklet for playback
4. Connects to Zoom's media server for audio send/receive

### After joining
- Footer button changes from headphone icon to microphone icon
- Aria-label changes from "Join Audio" to "Mute" or "Unmute"
- Audio elements in DOM start carrying actual audio data

## Question 7: Can a Bot Join Audio Receive-Only Without getUserMedia?

**Technically possible at the WebRTC level, practically blocked by Zoom's UI.**

Zoom's architecture (from webrtchacks analysis):
```
RECEIVE: WebSocket/DataChannel -> WASM Decoder -> AudioWorklet -> WebAudio destination
SEND:    getUserMedia -> WebAudio capture -> WASM Encoder -> WebSocket/DataChannel
```

The receive path is independent of getUserMedia. However:
- Zoom's "Join Audio by Computer" button triggers getUserMedia AND initializes the receive pipeline as a single action
- There is no UI to join audio receive-only
- The `--use-fake-device-for-media-stream` Chromium flag satisfies getUserMedia with a fake device, effectively making it receive-only without real mic input

**Recommended approach for recorder bots:**
1. Use `--use-fake-device-for-media-stream` + `--use-fake-ui-for-media-stream` (already set)
2. DON'T click "Continue without microphone and camera" — instead, let the permission dialog auto-grant via fake UI flag
3. After admission, click "Join Audio" footer button -> "Join Audio by Computer"
4. getUserMedia succeeds (fake device), audio receive pipeline starts, bot can hear everyone
5. Bot is "muted" by default (fake device produces silence), so it doesn't disrupt the meeting

([source](https://webrtchacks.com/zoom-avoids-using-webrtc/))

## Recommended Fix Strategy

### Option A: Fix the pre-join flow (preferred)
**Don't click "Continue without microphone and camera" for recorder bots either.** Instead:
1. Let `--use-fake-ui-for-media-stream` auto-grant the permission dialog (it should auto-dismiss)
2. If permission dialog still appears, click "Allow" instead of "Continue without..."
3. In pre-join preview, mute the mic (already done in join.ts:148-158)
4. Click Join
5. Audio should be connected from the start

This avoids the two-step post-admission audio join entirely.

### Option B: Fix the post-admission flow (fallback)
Keep clicking "Continue without microphone and camera" but make `prepareZoomWebMeeting()` reliably join audio after admission:
1. Wait for meeting to fully load (check for `zoomLeaveButtonSelector` visibility)
2. Click footer audio button (`button.join-audio-container__btn`)
3. Wait for dialog, click "Join Audio by Computer" / "Join with Computer Audio"
4. Verify audio joined: check footer button aria-label changed to "Mute"/"Unmute"
5. If verification fails, retry with page refresh as last resort

### Option C: URL parameter (experimental)
Add `prefer=1` to the web client URL in `buildZoomWebClientUrl()`:
```typescript
wcUrl.searchParams.set('prefer', '1');
```
Known reliability issues — should be tested but not relied upon as sole solution.

### Recommended: Option A + Option B as fallback
1. Try Option A first (don't dismiss permission dialog)
2. After admission, verify audio is connected (check footer button aria-label)
3. If not connected, fall back to Option B (post-admission audio join)
4. Add Option C as a belt-and-suspenders measure

## Dead Ends to Avoid

1. **PulseAudio capture for Zoom:** Chrome doesn't route Zoom WebRTC audio through PulseAudio. Per-speaker ScriptProcessor is the only working path. (confirmed in feature-log.md)
2. **Caption-based transcription:** Works but limited — many orgs disable captions, and captions don't provide per-speaker audio for custom transcription.
3. **`ZoomMtg.showJoinAudioFunction({ show: false })`:** Only hides the dialog, doesn't join audio. SDK-only, not applicable to web client automation.
4. **Waiting >10s for `#pc-join` click:** This is from the SDK, selector may not exist in native web client. Verify before relying on it.

## Sources

- [webrtchacks: How Zoom's web client avoids using WebRTC](https://webrtchacks.com/zoom-avoids-using-webrtc/)
- [Zoom Forum: Auto-enable speaker audio without Join Audio button](https://devforum.zoom.us/t/auto-enable-speaker-audio-without-clicking-join-audio-button-in-meeting-sdk/114650)
- [Zoom Forum: Join Audio / Leave Computer Audio unreliable](https://devforum.zoom.us/t/join-audio-leave-computer-audio-buttons-dont-work-reliably/81658)
- [Zoom Forum: Auto-join computer audio](https://devforum.zoom.us/t/web-sdk-connecting-the-user-with-computer-audio-automatically-when-joining/2682)
- [Zoom Forum: prefer=1 fails](https://devforum.zoom.us/t/zoom-web-client-fails-to-connect-audio-when-using-prefer-1/14037)
- [Zoom Forum: Join Audio by Computer disabled ~15%](https://devforum.zoom.us/t/bug-meeting-sdk-web-v5-1-2-join-audio-by-computer-button-disabled-15-of-meetings/142317)
- [Zoom Forum: Speaker doesn't work with Puppeteer](https://devforum.zoom.us/t/the-speaker-sometimes-does-not-work-when-using-puppeteer-with-a-fake-media-device/132367/17)
- [Recall.ai: How to build a Zoom bot](https://www.recall.ai/blog/how-to-build-a-zoom-bot)
- [Recall.ai: How to join Zoom using Puppeteer](https://www.recall.ai/blog/how-to-join-zoom-using-puppeteer)
- [screenappai/meeting-bot](https://github.com/screenappai/meeting-bot)
