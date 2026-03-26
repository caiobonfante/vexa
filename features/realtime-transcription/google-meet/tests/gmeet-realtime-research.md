# Google Meet Real-Time Audio/Video Architecture — Deep Research

**Date:** 2026-03-25
**Researcher:** Agent (researcher role)
**Context:** Building a meeting bot that joins Google Meet via Playwright browser automation for real-time transcription with per-speaker audio capture.

---

## 1. WebRTC Architecture in Google Meet

### 1.1 SFU (Selective Forwarding Unit) Architecture

Google Meet uses an **SFU topology**, not mesh or MCU. Each participant connects only to Google's SFU servers, which selectively forward relevant streams to other participants.

**Key characteristics:**
- The SFU receives individual media streams from each participant
- It selectively forwards the active/relevant streams
- Reduces client processing and bandwidth compared to mesh (P2P)
- Unlike MCU, no server-side mixing for video (audio is partially mixed via virtual streams)

Source: [Meet Media API Virtual Streams](https://developers.google.com/workspace/meet/media-api/guides/virtual-streams)

### 1.2 Audio Stream Architecture — "Virtual Media Streams"

Google Meet does NOT send one audio stream per participant. Instead, it uses a **fixed set of 3 virtual audio streams** regardless of conference size.

**How it works:**
- The SFU maintains exactly **3 audio SSRCs** (Synchronization Sources)
- These 3 streams carry audio from the **3 loudest participants** at any given moment
- When speaker activity changes, Meet **dynamically switches** which participant's audio flows through each SSRC
- The **SSRC values never change** for the life of the session (atypical for WebRTC)
- Each participant is assigned a unique **CSRC (Contributing Source)** identifier upon joining, which remains constant until they leave
- The CSRC in RTP packet headers identifies the **true source** of audio, even as SSRCs are reused

**Scenarios:**
| Condition | Behavior |
|-----------|----------|
| More participants than SSRCs (>3) | 3 loudest get the 3 SSRCs; switches dynamically |
| Fewer participants than SSRCs (<3) | Each gets a dedicated SSRC; unused ones idle |
| Exactly 3 participants | 1:1 persistent mapping |

**Critical implication for browser bots:** When you intercept audio in the browser, you get the output of this virtual stream system. The browser receives **3 audio tracks** via WebRTC, and Google Meet's JavaScript creates separate `<audio>` DOM elements from these tracks. However, the 3 tracks do NOT permanently map to 3 specific participants -- they are dynamically multiplexed.

Source: [Meet Media API Virtual Streams](https://developers.google.com/workspace/meet/media-api/guides/virtual-streams), [How Google Meet Implements Audio using Mix-Minus](https://www.red5.net/blog/how-google-meet-implements-audio-using-mix-minus-with-webrtc/)

### 1.3 DOM Structure for Audio/Video Elements

Based on live inspection from this codebase (see `services/vexa-bot/core/src/index.ts:1758-1878` and `platforms/googlemeet/recording.ts`):

**Audio elements:**
- Google Meet creates separate `<audio>` DOM elements, each with `srcObject = MediaStream` containing audio tracks
- These are discovered via: `document.querySelectorAll('audio, video').filter(el => !el.paused && el.srcObject.getAudioTracks().length > 0)`
- The number of active audio elements corresponds to the virtual stream system (typically up to 3 for audio)
- Elements may be recycled as participants join/leave

**Participant tiles:**
- Each visible participant gets a `div[data-participant-id]` container
- Speaking indicators are CSS class changes on elements within these containers
- Names are in `span.notranslate` elements
- The `[data-audio-level]` attribute on some elements indicates speaking when not "0"

**Key selectors (from `selectors.ts`, subject to change):**

| Selector | Purpose |
|----------|---------|
| `div[data-participant-id]` | Participant tile container |
| `span.notranslate` | Participant name text |
| `[data-self-name]` | Self-name attribute |
| `[data-audio-level]:not([data-audio-level="0"])` | Speaking indicator (semantic, survives CSS rotation) |
| `.Oaajhc` | Speaking animation class (obfuscated, may change) |
| `.HX2H7`, `.wEsLMd`, `.OgVli` | Alternative speaking classes (obfuscated) |
| `.gjg47c` | Silence class (obfuscated) |
| `button[aria-label="Leave call"]` | Leave button |
| `[jsname="BOHaEe"]` | Meeting container |

**WARNING:** Obfuscated class names (`Oaajhc`, `HX2H7`, etc.) rotate with Google Meet UI deployments. The semantic selector `[data-audio-level]` is more stable.

### 1.4 MediaStream Architecture in Browser

The flow from WebRTC to DOM:

```
Google Meet SFU
    |
    v (WebRTC PeerConnection, 3 audio transceivers)
RTCPeerConnection.ontrack events
    |
    v (Google Meet's JavaScript)
<audio> DOM elements (srcObject = MediaStream)
    |
    v (Our bot: startPerSpeakerAudioCapture)
AudioContext per element -> ScriptProcessorNode -> callback to Node.js
```

The browser receives up to 3 audio tracks via WebRTC. Google Meet's client-side JavaScript creates `<audio>` elements and assigns each track's MediaStream as `srcObject`. Our bot discovers these elements and creates per-element audio capture pipelines.

---

## 2. Audio Capture Approaches

### 2.1 ScriptProcessorNode vs AudioWorklet

**Current codebase uses ScriptProcessorNode.** Here is the comparison:

| Aspect | ScriptProcessorNode | AudioWorklet |
|--------|-------------------|--------------|
| Thread | Main thread (blocks UI) | Separate audio rendering thread |
| Latency | Higher (main thread contention) | Lower (dedicated thread) |
| Status | **Deprecated** since Chrome 64 (2018) | Standard since Chrome 66 |
| Still works? | Yes, as of Chrome 2025-2026 | Yes |
| Complexity | Simple callback API | Requires separate module file, MessagePort communication |
| Data access | Direct Float32Array in callback | Float32Array in process() method |
| GC risk | Must hold reference to prevent collection | Same risk |
| Cross-origin | Works in page.evaluate | Requires addModule() with URL, more complex in Playwright context |

**Recommendation:** ScriptProcessorNode works and is simpler for Playwright injection. AudioWorklet is the future-proof choice but significantly more complex to inject via `page.evaluate()` because it requires:
1. Registering a worklet module via `audioContext.audioWorklet.addModule(url)`
2. The module must be served from a URL (can't inline it trivially)
3. Communication via MessagePort instead of direct callback

For a browser bot where the main thread isn't doing UI rendering, the ScriptProcessorNode's main-thread limitation is less impactful. However, Chrome could remove ScriptProcessorNode in a future release without warning.

**Mitigation strategy:** If ScriptProcessorNode is removed, the AudioWorklet approach would require injecting a Blob URL:
```javascript
const workletCode = `class Processor extends AudioWorkletProcessor { ... }`;
const blob = new Blob([workletCode], { type: 'application/javascript' });
const url = URL.createObjectURL(blob);
await audioContext.audioWorklet.addModule(url);
```

Sources: [MDN ScriptProcessorNode](https://developer.mozilla.org/en-US/docs/Web/API/ScriptProcessorNode), [Chrome AudioWorklet](https://developer.chrome.com/blog/audio-worklet), [Audio Worklet Design Patterns](https://developer.chrome.com/blog/audio-worklet-design-pattern/)

### 2.2 How Competitors Capture Audio from Google Meet

#### Recall.ai — Bot-Based Approach
- Joins as a WebRTC participant via headless browser
- Open-source reference: [recallai/google-meet-meeting-bot](https://github.com/recallai/google-meet-meeting-bot)
- Their open-source bot uses **caption scraping** (DOM MutationObserver on `[aria-live]` caption regions), NOT audio capture
- Their commercial product provides "real-time audio and video streams" via WebSocket to customers (16kHz, mono, signed 16-bit PCM)
- Also offers a "Desktop Recording SDK" for bot-free capture from the user's device

Source: [Recall.ai - How to Build a Google Meet Bot](https://www.recall.ai/blog/how-i-built-an-in-house-google-meet-bot), [Recall.ai Google Meet Bot API](https://www.recall.ai/product/meeting-bot-api/google-meet)

#### Fireflies.ai — Google Meet SDK (Bot-Free)
- Uses the **Google Meet Media API** (SDK integration)
- "Google's official SDK to securely access real-time audio and video streams"
- Bot-free: no visible participant in the meeting
- Requires domain-level approval and participant consent
- Recording happens "securely in the background"
- Every attendee must approve; one approval starts recording

Source: [Fireflies Google Meet SDK Integration](https://guide.fireflies.ai/articles/3309351579-integrate-google-meet-sdk-with-fireflies-for-bot-free-meeting-recording)

#### tl;dv — Bot-Based Approach
- Bot joins the meeting as a visible participant
- Records both audio and video
- Generates AI summaries post-meeting
- Free tier includes unlimited recording/transcription

#### Granola — Device-Level Capture
- Captures audio from the user's device (not a bot)
- No meeting participant added
- Works across all platforms
- Privacy-first: audio processed locally

#### Otter.ai — Mixed Approach
- Offers both bot-based and device capture
- Live transcription during meetings
- Chrome extension option

### 2.3 RTCPeerConnection Interception

**Can you intercept RTCPeerConnection to get individual streams before mixing?**

This is what our Teams implementation does (`addInitScript` to hook RTCPeerConnection.prototype). For Google Meet:

- **Possible** to intercept `ontrack` events on RTCPeerConnection
- You would see the 3 virtual audio tracks being added
- However, these are the same 3 virtual streams that end up in `<audio>` elements -- no additional per-participant separation
- The CSRC values in RTP headers could theoretically identify which participant is on which stream, but accessing RTP-level data from JavaScript requires `RTCRtpReceiver.getContributingSources()` or `getSynchronizationSources()`
- **`getContributingSources()`** returns CSRC info including audio levels, which COULD be used for speaker identification

**This is an underexplored opportunity in the current codebase:** Instead of relying on DOM speaking indicators, we could use `RTCRtpReceiver.getContributingSources()` to get CSRC-based speaker identification directly from WebRTC, bypassing fragile DOM selectors entirely.

### 2.4 WebAudio API for Splitting Mixed Audio

If you only have a single mixed audio stream, the WebAudio API cannot split it into per-speaker channels. That requires diarization (pyannote, WhisperX). However, Google Meet's 3-stream virtual architecture means you already have partial separation -- the 3 loudest speakers are on separate tracks at any given moment.

---

## 3. Speaker Identification

### 3.1 DOM-Based Speaking Indicators

The current implementation uses two parallel approaches:

**A. MutationObserver on class changes:**
- Watches `[data-participant-id]` containers for class attribute mutations
- Speaking classes: `Oaajhc`, `HX2H7`, `wEsLMd`, `OgVli` (obfuscated, subject to rotation)
- These classes appear/disappear on elements within participant tiles when speaking

**B. Polling fallback (500ms interval):**
- Queries speaking indicators on all participant tiles
- Primary: `[data-audio-level]:not([data-audio-level="0"])` -- semantic, more stable
- Secondary: speaking animation classes (obfuscated)

**C. `__vexaGetAllParticipantNames()` exposed function:**
- Returns `{ names: {participantId: name}, speaking: [names] }`
- Called by Node.js `speaker-identity.ts` during audio processing
- Names extracted from `span.notranslate` or `[data-self-name]`

### 3.2 Per-Stream vs Mixed Stream Speaker ID

| Approach | Per-Stream (current) | Mixed Stream | CSRC-Based (proposed) |
|----------|---------------------|-------------|----------------------|
| How it works | Correlate audio activity on track N with DOM speaking indicator | Post-hoc diarization (pyannote) | Read RTCRtpReceiver.getContributingSources() |
| Accuracy | Good when 1 speaker active; fails during overlap | Moderate; depends on speaker similarity | Exact participant ID from RTP headers |
| Latency | Real-time | Post-meeting or high-latency | Real-time |
| Fragility | DOM selectors change with Meet updates | Stable (no DOM dependency) | Very stable (WebRTC standard API) |
| Limitation | Only works with single speaker active | CPU-intensive, needs GPU for real-time | Requires mapping CSRC to participant name |

### 3.3 CSRC-Based Speaker Identification (Novel Approach)

**This is a significant research finding.** The WebRTC API provides `RTCRtpReceiver.getContributingSources()` which returns:

```typescript
interface RTCRtpContributingSource {
  source: number;      // CSRC identifier (unique per participant in Meet)
  timestamp: number;   // RTP timestamp
  audioLevel: number;  // 0.0 to 1.0
}
```

Google Meet assigns each participant a unique CSRC that remains constant for the session. By polling `getContributingSources()` on each audio receiver, we could:

1. Know exactly which participant's audio is on each virtual stream at any moment
2. Detect speaker changes without DOM scraping
3. Get audio level per participant (useful for VAD)

**The remaining challenge:** Mapping CSRC values to participant names. The CSRC is a numeric identifier, not a name. Options:
- Use the Meet Media API's participant metadata (requires API enrollment)
- Correlate CSRC values with DOM participant tiles using timing (when a tile's speaking indicator activates, check which CSRC just became active)
- Use `RTCRtpReceiver.getSynchronizationSources()` alongside participant roster

This approach would be **significantly more robust** than DOM class scraping, as it uses standard WebRTC APIs rather than obfuscated Google Meet CSS classes.

### 3.4 Real-Time Diarization Approaches

If per-speaker streams aren't available (fallback scenarios):

| Tool | Real-Time? | Accuracy | GPU Required? |
|------|-----------|----------|---------------|
| pyannote 4.0 | Near-real-time | Good for non-overlapping | Yes |
| WhisperX | Batch only (380-520ms) | Good | Yes |
| whisper-diarization | Batch only | Good | Yes |
| Silero VAD | Real-time | VAD only (no diarization) | No |

For Google Meet specifically, diarization is a fallback -- the per-stream architecture makes it unnecessary when working correctly.

---

## 4. Known Challenges and Solutions

### 4.1 Google Meet Anti-Bot Detection

**Current status (2025-2026):**
- Google Meet does NOT appear to have aggressive bot-detection CAPTCHA for meeting joins
- The main barriers are **organizational policies** (domain-restricted meetings, external participant blocks)
- Google accounts used by bots may trigger **login CAPTCHAs** or **2FA challenges**
- The pre-join page requires a name input and "Ask to join" click -- standard UI automation

**Mitigations in current codebase:**
- Pre-authenticated browser sessions (stored auth state)
- `--use-fake-ui-for-media-stream` Chrome flag for media permissions
- Bot name entered via `page.fill()` on name input
- Camera/mic muted before joining

**Risks:**
- Google could add bot detection at any time (fingerprinting, behavioral analysis)
- Login session expiry forces re-authentication
- UI selector changes break join flow

Source: [Recall.ai - Puppeteer Google Meet Bot](https://www.recall.ai/blog/puppeteer-google-meet-bot)

### 4.2 Audio Element Lifecycle and GC

**This is a critical issue.** Web Audio API `ScriptProcessorNode` instances are garbage collected if no JavaScript reference holds them.

**Current protection (in `startPerSpeakerAudioCapture`):**
- All AudioContext, source, and processor references stored on `window.__vexaAudioStreams`
- Track `ended` event listeners log when MediaStreamTrack stops
- Connected stream IDs tracked in `Set<string>` to prevent double-binding
- 15-second re-scan interval discovers new audio elements (late joiners)
- 30-second health monitor detects stale/silent streams

**Known failure modes:**
- If `window.__vexaAudioStreams` is cleared or overwritten, all audio capture stops silently
- MediaStreamTrack `ended` events fire when participant leaves or when Meet reassigns virtual streams
- AudioContext may be suspended by Chrome's autoplay policy (though headless Chrome is less strict)

### 4.3 Participant Join/Leave Handling

**Current approach:**
- 15-second periodic re-scan of DOM for new `<audio>` elements
- When a new MediaStream is found (not in `connectedStreamIds`), a new AudioContext + ScriptProcessor pipeline is created
- When a track ends, `connectedStreamIds` is cleaned up
- Participant counting via `[data-participant-id]` tiles with "Leave call" button fallback
- Screen share mode hides participant tiles -- fallback uses last known count

**Gap:** When Google Meet reassigns a virtual stream (speaker changes from Alice to Bob on the same SSRC), the audio element may not change -- the same `<audio>` element now carries different participant audio. The current per-element index system would attribute Bob's audio to Alice's track until the speaking indicator voting system corrects it.

### 4.4 Selector Instability

Google Meet uses **obfuscated/compiled CSS class names** that change with UI deployments. The current selectors in `selectors.ts` include both:
- **Stable selectors:** `[data-participant-id]`, `[data-audio-level]`, `span.notranslate`, `button[aria-label="Leave call"]`
- **Unstable selectors:** `.Oaajhc`, `.HX2H7`, `.wEsLMd`, `.OgVli`, `.gjg47c`

**Best practice:** Prefer semantic selectors (`[data-audio-level]`, `aria-label`) over class-based selectors. The `[data-audio-level]:not([data-audio-level="0"])` selector for speaking detection is notably more robust.

---

## 5. API Alternatives

### 5.1 Google Meet REST API

**Status:** Generally Available (GA)
**Capabilities:**
- Create and manage meeting spaces
- Retrieve meeting metadata (participants, recordings)
- Webhook notifications for meeting lifecycle events
- Access recordings via Google Drive

**Limitations:**
- **Cannot access real-time audio/video**
- Cannot retrieve attendee emails directly
- Recording access depends on Workspace plan
- Requires sensitive OAuth scopes and security verification

Source: [Google Meet REST API Overview](https://developers.google.com/workspace/meet/api/guides/overview)

### 5.2 Google Calendar API

- Create calendar events with Google Meet links
- Manage invitations and attendees
- Useful for scheduling bot attendance
- Cannot access meeting media

### 5.3 Google Workspace Add-ons SDK for Meet

- Build add-on panels within the Google Meet UI
- Limited to UI extensions, not media access
- Useful for side-panel integrations

### 5.4 Meet Media API (Developer Preview)

**Status:** Developer Preview (NOT GA as of March 2026)
**Last documentation update:** March 2, 2026

**What it provides:**
- Real-time access to audio, video, and participant metadata via WebRTC
- Receive-only (cannot send media into the meeting)
- Uses the same SFU architecture: 3 virtual audio streams, 1-3 video streams
- CSRC-based participant identification in RTP headers
- Audio Level Indication headers for speaker detection

**Prerequisites (heavy):**
- Google Cloud project enrolled in Developer Preview Program
- OAuth principal enrolled
- **ALL conference participants** must be enrolled in Developer Preview
- Google Workspace account required
- Minimum mobile app versions: Android Meet 309, iOS Meet 308
- Restricted OAuth scopes requiring verification compliance
- Cannot connect to meetings with encryption or watermarks enabled

**Reference clients:**
- [TypeScript client](https://developers.google.com/workspace/meet/media-api/guides/ts) -- web-based, requires App Engine deployment
- [C++ client](https://developers.google.com/workspace/meet/media-api/guides/cpp) -- native
- [GitHub samples](https://github.com/googleworkspace/meet-media-api-samples) -- 84.9% C++, 11.9% TypeScript

**Technical requirements:**
- Must support Opus codec for audio
- Must support AV1, VP9, VP8 for video
- Must offer exactly 3 audio media descriptions
- Must implement WebRTC stack (no SDK provided)
- CORS restrictions require deployment (not localhost)
- "4-7 weeks" for security assessment and restricted scope approval

**Critical limitation:** Requiring ALL participants to be enrolled in the Developer Preview makes this impractical for production use with external participants. This is why Fireflies.ai's integration likely uses a different consent mechanism or has special partnership access.

**Consent model:**
- A participant from the organizing institution must consent
- Any participant can revoke consent at any time, immediately terminating the media stream
- No recovery mechanism after revocation

Sources: [Meet Media API Overview](https://developers.google.com/workspace/meet/media-api/guides/overview), [Meet Media API Concepts](https://developers.google.com/workspace/meet/media-api/guides/concepts), [Recall.ai Analysis of Meet Media API](https://www.recall.ai/blog/what-is-the-google-meet-media-api)

### 5.5 Comparison of API Approaches

| Approach | Real-Time Audio | Per-Speaker | Bidirectional | Approval Burden | Production Ready |
|----------|----------------|-------------|---------------|----------------|-----------------|
| REST API | No | No | N/A | Moderate | Yes |
| Calendar API | No | No | N/A | Low | Yes |
| Meet Media API | Yes | Via CSRC | Receive-only | **Very High** | No (Dev Preview) |
| Browser Bot | Yes | Via DOM scraping | Yes (can speak/chat) | Low | Yes (fragile) |
| Chrome Extension | Yes | Via tabCapture | No | Low | Yes (user-installed) |

---

## 6. Competitor Deep Dive

### 6.1 Recall.ai Google Meet Implementation

**Two products:**

1. **Meeting Bot API (commercial):**
   - Headless browser joins as participant
   - Per-participant audio streams delivered via WebSocket (16kHz, mono, 16-bit PCM)
   - Speaker identification included
   - Full bidirectional capability
   - Handles infrastructure scaling, browser management

2. **Open-source reference bot:** [github.com/recallai/google-meet-meeting-bot](https://github.com/recallai/google-meet-meeting-bot)
   - Playwright-based (not Puppeteer despite blog title)
   - **Caption scraping only** -- no audio capture
   - MutationObserver on `[aria-live]` caption regions
   - Speaker names from caption attribution badges (`.NWpY1d`, `.xoMHSc` selectors)
   - Segments: `{speaker, text, start, end}` flushed to PostgreSQL
   - Post-meeting OpenAI summarization
   - Authentication via stored `auth.json` from manual login

**Key insight from Recall.ai:** Their open-source bot intentionally avoids audio capture complexity by using Google Meet's built-in captions. Their commercial product does capture audio but the implementation is proprietary. The caption-scraping approach is simpler but depends on Google Meet's caption accuracy and has no access to raw audio.

### 6.2 Fireflies.ai Google Meet Integration

- Uses the **Google Meet Media API (SDK)** for bot-free recording
- This is currently the only known competitor using the official Media API in production
- Suggests they have early/partnership access beyond the standard Developer Preview
- Consent-based: recording starts when one participant approves
- Chrome extension available as alternative

### 6.3 tl;dv

- Bot-based approach (visible participant)
- Chrome extension: [Chrome Web Store](https://chromewebstore.google.com/detail/record-transcribe-chatgpt/lknmjhcajhfbbglglccadlfdjbaiifig)
- Records audio and video
- Free unlimited transcription/recording
- AI summaries post-meeting

### 6.4 Granola

- Device-level audio capture (no bot)
- Privacy-first: local processing
- Works across all platforms without integration
- Not a meeting participant

---

## 7. Recommendations for Vexa

### 7.1 Immediate (Current Architecture)

The current browser bot approach with per-element ScriptProcessorNode is sound. Improvements:

1. **Investigate CSRC-based speaker identification** as replacement/supplement for DOM class scraping:
   ```javascript
   const receivers = peerConnection.getReceivers();
   for (const receiver of receivers) {
     const csrcs = receiver.getContributingSources();
     // csrcs[].source = participant CSRC, csrcs[].audioLevel = volume
   }
   ```
   This requires intercepting the RTCPeerConnection instance via `addInitScript`.

2. **Prioritize `[data-audio-level]` selector** over obfuscated class names for speaking detection. This is a semantic attribute that's more stable.

3. **Prepare AudioWorklet migration path** for when ScriptProcessorNode is removed. The Blob URL approach works:
   ```javascript
   const workletCode = `class CaptureProcessor extends AudioWorkletProcessor {
     process(inputs) {
       const data = inputs[0][0];
       if (data) this.port.postMessage(Array.from(data));
       return true;
     }
   }
   registerProcessor('capture', CaptureProcessor);`;
   const blob = new Blob([workletCode], {type: 'application/javascript'});
   await ctx.audioWorklet.addModule(URL.createObjectURL(blob));
   ```

### 7.2 Medium-Term

4. **Explore caption scraping as supplementary speaker ID** (like Recall.ai's open-source approach). Google Meet's built-in captions already have speaker attribution. Using both audio capture AND caption scraping provides redundant speaker identification.

5. **Monitor Meet Media API** for GA release. When it exits Developer Preview and drops the "all participants enrolled" requirement, it becomes the best approach for receive-only bots.

### 7.3 Understanding the Virtual Stream Limitation

**Critical architectural insight:** Google Meet's 3 virtual streams mean that in meetings with >3 participants, some participants' audio will time-share the same SSRC. The audio element at index 0 might carry Alice's audio for 5 seconds, then Bob's for the next 5 seconds.

The current voting system handles this correctly IF:
- The DOM speaking indicator updates when the virtual stream switches speakers
- Voting captures the correlation between "track N has audio" and "participant X is speaking"

However, there's a subtle race condition: audio may arrive on a track before the DOM indicator updates. This is why the CSRC approach would be superior -- it has the speaker identity embedded in the audio packets themselves.

### 7.4 Cross-Platform Comparison (Updated)

| Aspect | Google Meet | MS Teams | Zoom |
|--------|-----------|----------|------|
| Audio architecture | 3 virtual streams (SFU) | Single mixed stream | Per-participant `<audio>` elements |
| Per-speaker separation | Via virtual streams (partial) | Via caption boundaries | Native DOM elements |
| Speaker identification | DOM scraping / CSRC | Caption author | Active speaker DOM |
| Audio elements in DOM | Up to 3 `<audio>` | 1 `<audio>` | N `<audio>` (one per participant) |
| ScriptProcessor pipeline | 3 instances | 1 instance | N instances |
| Voting system | Required (track-to-speaker mapping) | Not needed (captions provide names) | Required (DOM traversal) |
| Official API | Meet Media API (Dev Preview) | N/A | RTMS (GA) |
| Caption scraping viable? | Yes (built-in captions available) | Yes (primary approach) | Limited |

---

## 8. External Dead Ends and Known Issues

### 8.1 Known Dead Ends

- **[EXTERNAL] Google Meet does not expose per-participant raw audio via Web SDK or any client-side API.** The virtual stream system means you get at most 3 mixed/multiplexed streams. Source: [Recall.ai blog](https://www.recall.ai/blog/how-to-integrate-with-google-meet)
- **[EXTERNAL] Meet Media API requires ALL participants enrolled in Dev Preview.** This makes it unusable for production with external participants as of March 2026.
- **[EXTERNAL] Caption selectors (`.NWpY1d`, `.xoMHSc`) are equally fragile as speaking class selectors.** Google rotates both regularly.
- **[EXTERNAL] Localhost deployment doesn't work for Meet Media API due to CORS.** Requires App Engine or similar deployment.

### 8.2 Open Questions

1. Does Google Meet's `[data-audio-level]` attribute update synchronously with the virtual stream speaker switching?
2. Can `RTCRtpReceiver.getContributingSources()` be called from a Playwright `page.evaluate()` context, or does it require `addInitScript` to capture the PeerConnection first?
3. When Fireflies says "Google Meet SDK" -- are they using the Developer Preview Media API with special access, or a different SDK?
4. How does the 3-stream limit affect transcription quality in meetings with 5+ active speakers?

---

## Sources

- [Meet Media API Overview](https://developers.google.com/workspace/meet/media-api/guides/overview)
- [Meet Media API Concepts](https://developers.google.com/workspace/meet/media-api/guides/concepts)
- [Meet Media API Virtual Streams](https://developers.google.com/workspace/meet/media-api/guides/virtual-streams)
- [Meet Media API TypeScript Quickstart](https://developers.google.com/workspace/meet/media-api/guides/ts)
- [Google Meet Media API Samples (GitHub)](https://github.com/googleworkspace/meet-media-api-samples)
- [Recall.ai - How to Build a Google Meet Bot](https://www.recall.ai/blog/how-i-built-an-in-house-google-meet-bot)
- [Recall.ai - Puppeteer Google Meet Bot](https://www.recall.ai/blog/puppeteer-google-meet-bot)
- [Recall.ai - How to Integrate with Google Meet](https://www.recall.ai/blog/how-to-integrate-with-google-meet)
- [Recall.ai - What is the Google Meet Media API](https://www.recall.ai/blog/what-is-the-google-meet-media-api)
- [Recall.ai Google Meet Bot (GitHub)](https://github.com/recallai/google-meet-meeting-bot)
- [Recall.ai Google Meet Bot API](https://www.recall.ai/product/meeting-bot-api/google-meet)
- [Fireflies Google Meet SDK Integration](https://guide.fireflies.ai/articles/3309351579-integrate-google-meet-sdk-with-fireflies-for-bot-free-meeting-recording)
- [How Google Meet Implements Audio using Mix-Minus](https://www.red5.net/blog/how-google-meet-implements-audio-using-mix-minus-with-webrtc/)
- [MDN ScriptProcessorNode](https://developer.mozilla.org/en-US/docs/Web/API/ScriptProcessorNode)
- [Chrome AudioWorklet](https://developer.chrome.com/blog/audio-worklet)
- [Audio Worklet Design Patterns](https://developer.chrome.com/blog/audio-worklet-design-pattern/)
- [Google Meet REST API Overview](https://developers.google.com/workspace/meet/api/guides/overview)
- [Talk-o-meter Chrome Extension (GitHub)](https://github.com/PaperCutSoftware/talk-o-meter)
