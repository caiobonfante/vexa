# Microsoft Teams Real-Time Audio/Video Implementation Research

Date: 2026-03-25
Context: Deep research for building a meeting bot that joins MS Teams via Playwright browser automation
Researcher: agent (researcher role)

---

## 1. Teams Audio/Video Architecture

### Protocol Stack

Teams uses **WebRTC** for real-time media transport in the browser client. The underlying protocol stack:

- **SRTP** (Secure Real-time Transport Protocol) for encrypted media packets
- **DTLS** for key exchange
- **ICE/STUN/TURN** for NAT traversal
- Audio codecs: **SILK** and **G.722** (16kHz, 16-bit PCM, 50 frames/sec = 20ms per frame = 320 samples/frame)
- Video codecs: **H.264** (supported frame sizes: 640x360, 1280x720, 1920x1080)

Source: [Microsoft Real-time Media Concepts](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/real-time-media-concepts)

### SFU Architecture

Teams uses an **SFU (Selective Forwarding Unit)** architecture, NOT an MCU:

- The SFU receives media streams from each participant and selectively forwards them
- Audio is **NOT mixed server-side** for the official Graph API bot path (unmixed audio available)
- However, the **browser client** receives a **single mixed audio stream** via one RTCPeerConnection
- Video streams are selectively forwarded; the client subscribes to specific participants
- The SFU handles "active speaker" and "dominant speaker" detection at the server level

**Critical distinction:** The Graph API real-time media platform provides per-speaker unmixed audio. The browser web client receives mixed audio. These are fundamentally different audio architectures for bots.

### Browser Client Audio Flow

```
Teams SFU Server
    |
    | Single RTCPeerConnection (mixed audio)
    v
Browser <audio> element
    |
    | AudioContext (16kHz)
    | ScriptProcessorNode (bufferSize=4096)
    v
Audio chunks (~256ms each)
    |
    | Speaker attribution needed (caption/DOM based)
    v
handleTeamsAudioData(speakerName, audioData)
```

### teams.live.com vs teams.microsoft.com

| Aspect | teams.microsoft.com | teams.live.com |
|--------|-------------------|---------------|
| Account type | Work/School (M365 Business/Enterprise) | Personal (Outlook.com, M365 Personal/Family) |
| Meeting links | `https://teams.microsoft.com/l/meetup-join/...` | `https://teams.live.com/meet/...` |
| Org policies | IT admin controls, conditional access | Limited admin controls |
| Bot lobby behavior | Controlled by org meeting policies | Default lobby behavior |
| Caption availability | Controlled by org policy, always available for bot's own session | Always available |
| DOM structure | Same new Teams client (WebView2-based) | Same new Teams client |
| ACS interop | Supported | **NOT supported** — ACS interop disabled for personal Teams |

Source: [Recall.ai Personal vs Business MS Teams](https://docs.recall.ai/docs/personal-vs-business-ms-teams), [ACS Teams Interop](https://learn.microsoft.com/en-us/azure/communication-services/concepts/join-teams-meeting)

**Key finding:** Both use the same new Teams client (v2, rebuilt on WebView2/Chromium). DOM selectors should be identical across both. The difference is in backend policies, not frontend rendering.

### New Teams Client (v2)

- Rebuilt using **Evergreen Microsoft Edge WebView2** (replacing Electron)
- Classic Teams client **ended availability July 1, 2025** -- all users on new client now
- Web access at `https://teams.microsoft.com` uses the same new client codebase
- The web client runs in standard Chromium/Edge browsers

Source: [New Microsoft Teams Client](https://learn.microsoft.com/en-us/microsoftteams/platform/resources/teams-updates)

---

## 2. Audio Capture via Browser Automation

### Current Vexa Implementation (Working)

Vexa's Teams bot uses an **RTCPeerConnection hook** via `page.addInitScript()`:

1. **Before Teams loads:** Monkey-patches `RTCPeerConnection` constructor
2. **On `track` event:** For each audio track, creates a hidden `<audio>` element with `srcObject = stream`
3. **Result:** Remote audio tracks become accessible as DOM `<audio>` elements
4. **Then:** ScriptProcessorNode (bufferSize=4096, sampleRate=16kHz) processes audio chunks

File: `services/vexa-bot/core/src/platforms/msteams/join.ts:184-266`

### Teams Delivers a SINGLE Mixed Audio Stream

Unlike Google Meet (separate `<audio>` per participant) and Zoom (also separate `<audio>` per participant), **Teams' browser client receives ONE mixed audio stream** via RTCPeerConnection. The RTCPeerConnection hook captures this single stream.

**Evidence from codebase:** The `startPerSpeakerAudioCapture()` pipeline (shared across GMeet/Zoom/Teams) finds injected `<audio>` elements, but in Teams there is typically only one element containing mixed audio from all participants.

### Speaker Separation from Mixed Stream

Since Teams provides mixed audio, speaker separation requires **external signals**:

1. **Live Captions (PRIMARY)** -- `[data-tid="author"]` + `[data-tid="closed-caption-text"]`
2. **DOM Speaking Indicators (FALLBACK)** -- `[data-tid="voice-level-stream-outline"]`
3. **Ring Buffer** -- 3s lookback for retroactive attribution when caption arrives ~1s after speech

The current architecture uses a **delay queue** (1s hold) + **staleness check** (1500ms threshold) to align audio chunks with caption speaker changes. See `ARCHITECTURE.md` and `BUFFER_PROPOSAL.md` in the ms-teams feature directory.

### ScriptProcessorNode vs AudioWorklet

The current implementation uses **ScriptProcessorNode** (deprecated but functional). Migration to AudioWorklet considerations:

| Aspect | ScriptProcessorNode | AudioWorklet |
|--------|-------------------|-------------|
| Thread | Main thread (can glitch) | Dedicated render thread |
| Deprecation | Deprecated, but still works in all browsers | Modern replacement |
| Buffer access | `onaudioprocess` callback | `process()` method in worklet |
| Communication | Direct function call | MessagePort (async) |
| Browser support | Universal | Chrome 66+, Firefox 76+, Safari 14.1+ |

**Recommendation:** ScriptProcessorNode works fine for our use case (16kHz mono, ~256ms chunks). AudioWorklet would reduce main-thread load but adds complexity with MessagePort communication. Not a priority upgrade unless we see audio glitches.

### Ring Buffer for Retroactive Attribution

Current implementation in `recording.ts`:

```
Audio chunk arrives -> Ring buffer (3s, 48000 samples at 16kHz)
                    -> Delay queue (1s hold)
                    -> On queue flush: check captionAge
                    -> captionAge < 1500ms: route to lastCaptionSpeaker
                    -> captionAge >= 1500ms: drop (speaker stopped)
```

Parameters (from ARCHITECTURE.md):
- Ring buffer: 3s (MAX_QUEUE_AGE_MS=3000)
- Audio delay: 1s
- Staleness threshold: 1500ms (AUDIO_DELAY + 500ms tolerance)
- Lookback on caption flush: 2s

---

## 3. Speaker Identification in Teams

### Live Captions (Primary Signal)

**Reliability: HIGH** -- Teams' server-side ASR produces captions with speaker attribution. When captions fire, you have 100% certainty about who is speaking.

DOM structure:
```html
<div data-tid="closed-caption-renderer-wrapper">
  <div data-tid="closed-caption-v2-virtual-list-content">
    <!-- HOST VIEW: items-renderer > ChatMessageCompact > author + text -->
    <!-- GUEST VIEW: (div) > author + text (NO items-renderer) -->
    <span data-tid="author">Alice (Guest)</span>
    <span data-tid="closed-caption-text">Hello everyone</span>
  </div>
</div>
```

**Stable selectors** (verified across both host and guest views):
- `[data-tid="closed-caption-renderer-wrapper"]` -- container
- `[data-tid="author"]` -- speaker name
- `[data-tid="closed-caption-text"]` -- spoken text

Caption behavior (from observed data, 273 events):
- Text grows word-by-word (~400ms between updates)
- Sentence splitting: Teams reformats in-place, text SHRINKS (not a speaker change)
- Speaker changes are atomic -- no overlap between two authors
- Caption delay: 1-2s from speech to first caption
- Overlapping speech: first speaker truncated mid-word

**Limitations:**
- ~1-2s delay from speech to caption appearance
- Captions must be enabled (bot does this automatically via menu clicks)
- Organization policies can disable captions (rare for bot's own session)
- Single-word utterances may not generate separate caption entries
- Captions only fire on real speech (benefit: no false positives from mic noise)

### DOM Speaking Indicators (Fallback Signal)

```css
/* Speaking indicator -- blue outline around participant tile */
[data-tid="voice-level-stream-outline"]

/* VDI frame occlusion -- Teams internal class */
.vdi-frame-occlusion
```

**Reliability: MEDIUM** -- `voice-level-stream-outline` activates on ANY mic input (noise, breathing, typing), not just speech. This makes it unreliable as a primary speaker signal.

**Key insight from BUFFER_PROPOSAL.md:**
> "False activations from mic noise -- DOM blue squares activate on ANY mic input: background noise, breathing, keyboard typing, paper rustling. This is NOT a speech signal -- it's a mic activity signal."

**Result:** Caption-driven routing is far superior to DOM-based routing. DOM indicators serve only as a fallback when captions are unavailable or delayed.

### MutationObserver Pattern

The bot observes caption changes via MutationObserver:

```javascript
const observer = new MutationObserver((mutations) => {
  // Process caption DOM changes
  // Extract author + text pairs
  // Update lastCaptionSpeaker + lastCaptionTimestamp
});
observer.observe(captionWrapper, {
  childList: true,
  subtree: true,
  characterData: true
});
```

Backup: 200ms polling interval as fallback (Teams may use virtual DOM updates that don't trigger mutations).

### Caption-Driven vs DOM-Driven Speaker Detection

| Aspect | Caption-driven | DOM-driven |
|--------|---------------|-----------|
| Accuracy | ~100% (server-side ASR) | ~60-70% (mic activity, not speech) |
| Latency | 1-2s delay | ~300ms |
| False positives | Zero | High (noise, breathing, typing) |
| Speaker name | Exact name from caption | Must scrape from participant tile |
| Availability | Requires caption enablement | Always available |
| Overlapping speech | Shows one speaker at a time | Multiple tiles can light up |

**Recommendation:** Caption-driven is the correct primary approach. DOM-driven is useful ONLY as a fallback or for detecting that someone might be speaking before the caption arrives (used with ring buffer lookback).

---

## 4. Teams Bot Framework (Official APIs)

### Microsoft Graph Communications API

The **official** path for Teams bots with media access. Two hosting models:

#### Service-Hosted Media Bots
- Microsoft handles all media processing
- Bot receives events (call started, participant joined, etc.) but NOT raw media
- No audio/video access -- only metadata
- Can be stateful or stateless

#### Application-Hosted Media Bots
- Bot receives **raw audio/video frames**
- 50 audio frames/sec (20ms each, 16kHz 16-bit PCM = 640 bytes/frame)
- 30 video frames/sec (H.264 or raw RGB24/NV12)
- **ReceiveUnmixedMeetingAudio** capability: per-speaker separate audio streams
- Active speaker / dominant speaker identification built-in

**Hard Requirements:**
- **C# / .NET only** -- no Node.js, Python, or other language support
- **Windows Server** on Azure (Cloud Service, VMSS, IaaS VM, or AKS)
- **Cannot be deployed as Azure Web App**
- Must use `Microsoft.Graph.Communications.Calls.Media` NuGet package
- SDK version must be < 3 months old (auto-deprecation)
- Each VM needs **instance-level public IP** (ILPIP)
- Minimum 2 CPU cores per VM (Dv2-series recommended)
- **Developer preview** status -- subject to change

Source: [Application-hosted Media Bots](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/requirements-considerations-application-hosted-media-bots)

#### Key capability: ReceiveUnmixedMeetingAudio

The Graph Communications Bot Media SDK supports receiving **unmixed per-speaker audio** in meetings. Each speaker's audio arrives as a separate buffer, tagged with participant identity. This eliminates the need for caption-based or DOM-based speaker attribution entirely.

**However:** This requires the full C#/.NET/Windows/Azure stack. Not viable for our Playwright/Node.js browser-based approach.

### Azure Communication Services (ACS)

ACS supports joining Teams meetings via web SDK (JavaScript/TypeScript), but with critical limitations:

- **No raw audio access** -- ACS JS Calling SDK does not support unmixed audio
- **No per-speaker separation** -- receives mixed audio only
- **No closed captions support** in the Calling SDK for Teams meetings
- Cannot start recording or transcription
- ACS users appear as "external" anonymous participants
- **NOT supported for personal Teams** (teams.live.com)
- Lobby behavior: must wait for admission unless policy says "Everyone can bypass"

Source: [ACS Teams Interop](https://learn.microsoft.com/en-us/azure/communication-services/concepts/join-teams-meeting)

**Verdict:** ACS is NOT a viable path for our use case. It doesn't provide audio access, speaker separation, or caption access.

### Teams AI Library

Updated in May 2025 at Build. Focus areas:
- Collaborative agents for Teams (Agent2Agent Protocol)
- Not designed for real-time audio processing
- Does NOT provide raw media access
- Intended for chat-based agents, not meeting transcription bots

**Verdict:** Teams AI Library is irrelevant for our audio capture use case.

### Microsoft's Recommended Path (as of Feb 2026)

Microsoft now explicitly discourages real-time media bots for AI agent scenarios:

> "Building AI agents for meetings? Real-time Media bots are not recommended for AI agent scenarios. Instead, use:
> - Microsoft Copilot Studio agents
> - Graph API meeting transcripts (post-meeting)
> - Meeting transcripts overview"

This signals Microsoft wants to own the in-meeting AI space (via Copilot) and push third parties to post-meeting access only.

---

## 5. Known Challenges

### Teams Anti-Bot Detection (CRITICAL -- May 2026)

**Microsoft is rolling out third-party bot detection and blocking:**

- **Mid-May 2026:** Targeted release rollout begins
- **Early-Mid June 2026:** General availability for all tenants
- External third-party bots will be **labeled distinctly in the lobby**
- Organizers must **explicitly and separately admit** detected bots
- New Teams admin meeting policy to control bot blocking
- Part of base Teams -- **enabled by default** for all tenants
- Admins can disable the block if they want to allow bots

**How detection works:**
- Microsoft checks participants as they attempt to join
- Detection occurs at the lobby stage
- Microsoft admits detection "is not perfect and might not pick up every third-party recording bot"
- Company plans to improve accuracy through customer reports and ongoing research

**Impact on Vexa:**
- Browser-based bots will likely be detected (joining as guest with non-standard behavior)
- Bots will need organizer approval to enter meetings
- This is a **significant business risk** -- meetings where the organizer doesn't explicitly approve the bot will fail
- Workaround: Educate users to approve the bot, or use signed-in bots with org approval
- This feature applies to Desktop, Mac, Linux, iOS, and Android

Sources:
- [Office365 IT Pros: Third-Party Recording Bots Blocked](https://office365itpros.com/2026/03/16/third-party-recording-bots/)
- [Bleeping Computer: Teams will tag third-party bots](https://www.bleepingcomputer.com/news/microsoft/microsoft-teams-will-tag-third-party-bots-in-meeting-lobbies/)
- [Help Net Security: Microsoft Teams bot detection](https://www.helpnetsecurity.com/2026/03/06/microsoft-teams-third-party-bot-identification/)
- [Windows Forum: Teams to Label External Bots](https://windowsforum.com/threads/microsoft-teams-to-label-external-third-party-bots-in-lobby-by-may-2026.404206/)

### Browser Requirements

- Teams web client works in **Chromium-based browsers** (Chrome, Edge) and Firefox
- New Teams client is built on WebView2 (Chromium-based)
- Our Playwright Chromium approach is correct and compatible
- No Edge-specific requirements for the web client

### Pre-Join Screen Handling

The bot must handle multiple pre-join states:
1. **Name input** -- enter bot display name
2. **Audio options** -- select "Computer audio" or "Don't use audio"
3. **Camera options** -- turn off camera, optionally select virtual camera
4. **Join button** -- click to enter lobby
5. **Lobby wait** -- "Someone will let you in shortly"
6. **Admission** -- detected by meeting control elements appearing

Selectors for all these states are defined in `selectors.ts`.

### Caption Enabling Automation

Bot must enable captions after joining via menu clicks:

**Guest path:** More (#callingButtons-showMoreBtn) -> Captions (direct toggle)
**Host path:** More -> Language and speech -> Show live captions

Both paths implemented in `captions.ts`. The bot handles both automatically.

### VDI Frame Occlusion

Teams uses `.vdi-frame-occlusion` CSS class internally. When participant tiles are occluded (scrolled out of view, minimized), speaking indicators may not update. This is a known limitation for DOM-based speaker detection.

### Recording Consent Banners

When a bot joins and starts recording, Teams shows consent banners to other participants. The bot doesn't need to handle these -- they're informational for other participants.

---

## 6. Competitor Approaches

### Recall.ai

- **Primary approach:** Browser automation with Playwright
- **Audio capture:** Caption scraping (not raw audio capture for standard product)
- **Speaker identification:** `span[data-tid="author"]` from captions
- **Architecture:** Two-server model (launcher + bot instances)
- **Caption processing:** MutationObserver + finalization detection (terminal punctuation)
- **Duplicate filtering:** Normalized text comparison
- **Teams URL handling:** Modifies query params (`msLaunch=false`, `suppressPrompt=true`) to bypass app-launch dialogs
- **Alternative product:** Desktop Recording SDK for scenarios where browser automation doesn't work
- Raised **$38M Series B** at $250M valuation (Sept 2025)

Sources:
- [Recall.ai: How to Build a Microsoft Teams Bot](https://www.recall.ai/blog/how-to-build-a-microsoft-teams-bot)
- [Recall.ai: Open Source Microsoft Teams Bot](https://www.recall.ai/blog/microsoft-teams-open-source-bot)
- [Recall.ai: Teams Overview](https://docs.recall.ai/docs/microsoft-teams)

### Otter.ai

- Joins Teams meetings automatically via calendar integration
- Provides real-time transcription with speaker identification
- Hit $100M ARR
- Likely uses a combination of browser automation and potentially Graph API for enterprise tenants
- Launched HIPAA compliance in 2025

### Fireflies.ai

- Auto-joins from calendar integration
- Real-time transcription across Teams, Zoom, GMeet
- Achieved $1B unicorn status on "Talk to Fireflies" real-time voice assistant
- Faces BIPA class-action lawsuit over recording practices

### tl;dv

- Works with Google Meet, Microsoft Teams, and Zoom
- Browser-based meeting recording and transcription
- Focus on finding information across meetings

### Read.ai

- Cross-platform transcription (Zoom, Meet, Teams)
- Meeting summaries and action items
- Listed among best AI meeting assistants for 2026

### MeetStream.ai

- Uses **Microsoft Graph media sockets + Microsoft.Psi framework** for Teams
- C#/.NET Windows nodes (Graph bot approach)
- `TeamsMediaStreamRouter` + `ParticipantMediaSource` components
- Can receive per-speaker unmixed audio via Graph SDK

### Open Source: screenappai/meeting-bot

- TypeScript + Node.js + Playwright
- Multi-platform (GMeet, Teams, Zoom)
- `POST /microsoft/join` endpoint
- Docker support with dev/prod Dockerfiles
- Automatic retry on admission failures

Source: [GitHub: screenappai/meeting-bot](https://github.com/screenappai/meeting-bot)

### Approach Summary

| Competitor | Approach | Audio Source | Speaker ID |
|-----------|----------|-------------|-----------|
| Recall.ai | Browser (Playwright) | Caption scraping | Caption author |
| Otter.ai | Browser + possibly Graph | Mixed + diarization | Proprietary |
| Fireflies | Browser automation | Mixed audio | Diarization |
| tl;dv | Browser automation | Mixed audio | Diarization |
| MeetStream | Graph API (.NET) | **Unmixed per-speaker** | Graph SDK |
| Vexa (us) | Browser (Playwright) | Mixed + RTCPeerConnection hook | Captions + DOM |

**Key insight:** Only MeetStream uses the Graph API for per-speaker audio. All browser-based competitors face the same mixed-audio challenge we do and rely on caption scraping or post-hoc diarization.

---

## 7. Recent Developments (2024-2026)

### Bot Detection Feature (March-June 2026) -- CRITICAL

See Section 5 above. This is the **single most important development** affecting all meeting bot providers. Timeline:
- March 2026: Announced
- Mid-May 2026: Targeted release
- Mid-June 2026: General availability

### Classic Teams End of Life (July 2025)

Classic Teams client no longer available as of July 1, 2025. All users on new Teams v2 client (WebView2-based). This is good for us -- single codebase to target, more consistent DOM.

### Teams AI Library Updates (May 2025)

- Agent2Agent Protocol (A2A) for inter-agent communication
- Focus on collaborative agents, NOT real-time media
- Not relevant for our audio capture use case

### Microsoft Copilot Integration

Microsoft is positioning Copilot as the official in-meeting AI. Third-party meeting bots are being squeezed:
- Bot detection feature pushes bots to explicit approval
- Graph API transcripts encouraged for post-meeting access
- Real-time media SDK in "developer preview" with no Python/Node.js support
- Microsoft recommending Copilot Studio agents instead

### Recall.ai Desktop SDK (2025)

Recall.ai launched a Desktop SDK as an alternative to browser bots -- likely in response to anticipated platform restrictions. This captures system audio at the OS level, bypassing browser-based detection.

---

## 8. Recommendations for Vexa Teams Implementation

### Short-term (current architecture is correct)

1. **Caption-driven routing is the right approach** -- matches what Recall.ai does, provides 100% speaker accuracy
2. **RTCPeerConnection hook for audio capture** -- already working, captures the mixed stream
3. **Ring buffer + delay queue** -- correct architecture for handling caption delay
4. **No need for Graph API pivot** -- would require C#/.NET/Windows, massive architecture change

### Medium-term (address bot detection)

1. **Bot detection (May-June 2026)** is the #1 risk. Mitigation options:
   - Support "signed-in" bots that use org-approved accounts
   - Provide clear UX for organizers to approve the bot
   - Explore whether detection can be avoided (Microsoft says detection "is not perfect")
   - Consider Desktop SDK approach (capture system audio instead of browser audio)
2. **Caption availability** -- ensure bot always enables its own captions after joining; this is per-participant and not affected by org policies that disable captions for others

### Long-term (strategic considerations)

1. **Graph API with unmixed audio** would be ideal but requires C#/.NET rewrite
2. **Desktop SDK approach** (like Recall.ai) could bypass both browser detection and DOM fragility
3. **Microsoft's direction** is to squeeze third-party bots -- plan for increasing resistance

### Technical Gaps to Address

1. **`resolveSpeakerName()` for Teams** -- currently relies on caption author, which includes "(Guest)" suffix. Should normalize names.
2. **Overlapping speech handling** -- captions show one speaker at a time; overlapping speech from the first speaker is lost
3. **Fast transitions (<0.5s gap)** -- minor audio bleed to previous speaker (acceptable per ARCHITECTURE.md)
4. **VDI occlusion** -- when tiles scroll out of view, DOM speaking indicators may not update (captions are unaffected)

---

## 9. Appendix: Key DOM Selectors (Verified March 2026)

### Caption System
```
[data-tid="closed-caption-renderer-wrapper"]     -- caption container
[data-tid="author"]                               -- speaker name
[data-tid="closed-caption-text"]                  -- caption text
[data-tid="closed-caption-v2-virtual-list-content"] -- virtual list
```

### Speaking Indicators
```
[data-tid="voice-level-stream-outline"]           -- voice activity (unreliable)
.vdi-frame-occlusion                              -- VDI internal class
```

### Meeting Controls
```
#callingButtons-showMoreBtn                       -- More menu button
#hangup-button                                    -- Leave/hangup button
button[data-tid="hangup-main-btn"]                -- Alternative leave button
```

### Join Flow
```
button:has-text("Join now")                       -- Join button
button:has-text("Continue")                       -- Continue button
input[placeholder*="name"]                        -- Name input field
radio[aria-label*="Computer audio"]               -- Audio selection
```

### URL Manipulation
```
?msLaunch=false&suppressPrompt=true               -- Bypass app-launch dialog (Recall.ai technique)
```

---

## Sources

- [Microsoft Real-time Media Concepts](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/real-time-media-concepts)
- [Application-hosted Media Bots Requirements](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/requirements-considerations-application-hosted-media-bots)
- [Teams Calls and Meetings Bots Overview](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/calls-meetings-bots-overview)
- [Graph Communications Bot Media SDK](https://microsoftgraph.github.io/microsoft-graph-comms-samples/docs/bot_media/index.html)
- [ACS Teams Meeting Interop](https://learn.microsoft.com/en-us/azure/communication-services/concepts/join-teams-meeting)
- [New Microsoft Teams Client](https://learn.microsoft.com/en-us/microsoftteams/platform/resources/teams-updates)
- [Classic Teams End of Availability](https://learn.microsoft.com/en-us/microsoftteams/teams-classic-client-end-of-availability)
- [Recall.ai: How to Build a Microsoft Teams Bot](https://www.recall.ai/blog/how-to-build-a-microsoft-teams-bot)
- [Recall.ai: Open Source Teams Bot](https://www.recall.ai/blog/microsoft-teams-open-source-bot)
- [Recall.ai: Microsoft Teams Overview](https://docs.recall.ai/docs/microsoft-teams)
- [Recall.ai: Personal vs Business MS Teams](https://docs.recall.ai/docs/personal-vs-business-ms-teams)
- [Office365 IT Pros: Third-Party Recording Bots Blocked](https://office365itpros.com/2026/03/16/third-party-recording-bots/)
- [Bleeping Computer: Teams will tag third-party bots](https://www.bleepingcomputer.com/news/microsoft/microsoft-teams-will-tag-third-party-bots-in-meeting-lobbies/)
- [Help Net Security: Microsoft Teams bot detection](https://www.helpnetsecurity.com/2026/03/06/microsoft-teams-third-party-bot-identification/)
- [Windows Forum: Teams to Label External Bots by May 2026](https://windowsforum.com/threads/microsoft-teams-to-label-external-third-party-bots-in-lobby-by-may-2026.404206/)
- [GitHub: screenappai/meeting-bot](https://github.com/screenappai/meeting-bot)
- [GitHub: Umer-2612/realtime-meeting-intelligence](https://github.com/Umer-2612/realtime-meeting-intelligence)
- [MeetStream: How to Build an Audio Transcription Bot](https://blog.meetstream.ai/tutorials/how-to-build-an-audio-transcription-bot-for-microsoft-teams/)
- [MeetStream: How to Capture Clean Audio Streams](https://blog.meetstream.ai/tutorials/how-to-capture-clean-audio-streams-from-meeting-bots/)
- [What's New in Microsoft Teams - May 2025](https://techcommunity.microsoft.com/blog/microsoftteamsblog/what%E2%80%99s-new-in-microsoft-teams--may-2025---build-edition/4414706)
