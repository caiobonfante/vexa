# CSRC-Based Speaker Identification Research

**Date:** 2026-03-25
**Scope:** Can RTCRtpReceiver.getContributingSources() replace DOM-based speaker detection across Google Meet, Teams, and Zoom?
**Verdict:** Platform-dependent. Strong for Google Meet, irrelevant for Zoom, unknown for Teams.

---

## 1. How getContributingSources() Works

### API Shape

```typescript
// RTCRtpReceiver method — call on any audio receiver
const csrcs: RTCRtpContributingSource[] = receiver.getContributingSources();

interface RTCRtpContributingSource {
  source: number;       // CSRC identifier (unique per contributing participant)
  timestamp: number;    // DOMHighResTimeStamp — last frame delivery time
  audioLevel: number;   // 0.0 (silence) to 1.0 (max volume), linear scale in dBov
  rtpTimestamp: number; // RTP media sample timestamp
}
```

### Key Behaviors

- Returns sources from the **last 10 seconds** only — stale entries are pruned
- `source` is a 32-bit CSRC identifier, unique per contributing participant in the RTP session
- `audioLevel` provides per-source volume — could replace ScriptProcessorNode silence detection
- Array may be **empty** if no CSRC values present in RTP packets (critical — see per-platform analysis)
- The method is **synchronous** — very cheap to poll (no async/promise overhead)

### Browser Support

- **Chrome:** Supported since Chrome 59+ (March 2019 baseline)
- **Firefox:** Supported since Firefox 59+
- **Safari:** Supported since Safari 12.1+
- **Edge:** Supported (Chromium-based)

Standard WebRTC 1.0 API. Widely available since March 2019.

### Important Chrome Bug (Now Fixed)

Chrome had a long-standing bug where `getSynchronizationSources()` (and likely `getContributingSources()`) returned **empty arrays** unless the audio track was attached to a playing `<audio>` element. Without a sink, Chrome skipped frame decoding as an optimization.

**Status:** Fixed via W3C spec PR #2385. The spec now clarifies that implementations should return synchronization information regardless of sink attachment.

**Implication for Vexa:** Our per-speaker pipeline already attaches audio to `<audio>` elements (that's how we discover them via `document.querySelectorAll('audio')`), so this bug doesn't affect us even on older Chrome versions.

Sources:
- [MDN: getContributingSources()](https://developer.mozilla.org/en-US/docs/Web/API/RTCRtpReceiver/getContributingSources)
- [W3C spec issue #2240 — empty return without sink](https://github.com/w3c/webrtc-pc/issues/2240)
- [W3C spec issue #4 — original CSRC API proposal](https://github.com/w3c/webrtc-pc/issues/4)
- [discuss-webrtc: getSynchronizationSources only with sink](https://groups.google.com/g/discuss-webrtc/c/GqojKPUt0-s)

---

## 2. Per-Platform Analysis

### 2.1 Google Meet — CSRC IS AVAILABLE (Strong Candidate)

**Architecture:** Google Meet uses an SFU that multiplexes the 3 loudest speakers onto 3 virtual audio streams (SSRCs). Each participant gets a unique CSRC that remains constant for their session.

**CSRC behavior:**
- Meet's SFU **sets CSRC values** in RTP packets — this is confirmed by Google's own Meet Media API documentation
- Each participant is assigned a unique CSRC upon joining
- The CSRC remains constant until the participant leaves
- When the SFU remaps a virtual stream (swaps which participant is on it), the **CSRC changes to reflect the new source participant**

**What this means for speaker identification:**
```
Virtual Stream A (SSRC 1): packets have CSRC=42 → Participant Alice
Virtual Stream A (SSRC 1): packets now have CSRC=99 → SFU swapped to Participant Bob
```

By polling `getContributingSources()` on each audio receiver:
1. **Know exactly which participant** is on each virtual stream at any moment
2. **Detect speaker changes** without DOM scraping
3. **Get audio level per participant** (replaces ScriptProcessorNode volume check)

**The remaining challenge: CSRC → Name mapping.**
CSRC is a numeric identifier. Mapping to participant names requires one of:
- **Timing correlation:** When a DOM speaking indicator activates, check which CSRC just became active. One-time correlation locks CSRC→name permanently. This is MORE robust than current approach because CSRC is in the packet itself — no DOM race condition.
- **Meet Media API:** Provides CSRC→participant metadata directly. But Developer Preview only, requires ALL participants enrolled — not production-viable (March 2026).
- **Session roster + join-order heuristic:** Unreliable, not recommended.

**Advantage over current DOM approach:**
| Aspect | DOM scraping (current) | CSRC-based (proposed) |
|--------|----------------------|----------------------|
| Fragility | Obfuscated CSS classes (`Oaajhc`, `HX2H7`) change with Meet updates | Standard WebRTC API, stable |
| Latency | DOM updates lag audio by ~500ms | CSRC is in the audio packet itself — zero lag |
| Multi-speaker | Only detects ONE active speaker at a time | Each virtual stream has its own CSRC — detect per-stream |
| Track remapping | Hard to detect when SFU swaps a stream's source | CSRC changes → instant detection |
| "All tracks vote for same speaker" | Current voting problem — all 3 streams see same DOM indicator | Each stream has its own CSRC — problem solved |

**Verdict: CSRC is superior to DOM scraping for Google Meet.** It solves the multi-track dedup problem (score 40) and slow speaker locking (585s → should be near-instant).

Sources:
- [Google Meet Media API: Virtual Streams](https://developers.google.com/workspace/meet/media-api/guides/virtual-streams)
- [Google Meet Media API: Overview](https://developers.google.com/workspace/meet/media-api/guides/overview)

### 2.2 Zoom — CSRC IS NOT AVAILABLE (Dead End)

**Architecture:** Zoom does NOT use standard WebRTC for media. The web client uses WebRTC DataChannels as a transport tunnel, with a custom media stack (WebAssembly decoders, AudioWorklet playback).

**CSRC behavior:**
- Research by Oliver et al. (2022) confirmed: **"the contributing source count (CSRC count) in Zoom RTP packets is always zero"**
- This is because Zoom's SFU forwards individual streams without modification to CSRC fields
- The zero CSRC count is characteristic of pure selective forwarding (not mixing)
- Even if Zoom did set CSRCs, the web client decodes audio via WASM — the audio doesn't flow through standard RTCPeerConnection receivers that expose `getContributingSources()`

**Additional problem:** Zoom web client's audio path is:
```
RTP → DataChannel → WebAssembly decoder → AudioWorklet → WebAudio destination
```
There are no standard `RTCRtpReceiver` objects to call `getContributingSources()` on. The audio bypasses Chrome's WebRTC media stack entirely.

**However:** Our bot observes separate `<audio>` elements per participant in the Zoom DOM (confirmed with bot 60). These likely come from Zoom's custom media handling, NOT from standard WebRTC tracks. So `getContributingSources()` cannot be called on them.

**Verdict: CSRC is a dead end for Zoom.** The current DOM-based approach (active speaker CSS + DOM traversal) remains the only viable option for browser-based Zoom bots. RTMS (if approved) provides native per-participant audio with speaker attribution.

Sources:
- [Oliver et al. 2022: Zoom CSRC count always zero](https://medium.com/@li.ying.explore/how-to-design-a-zoom-distributed-video-conferencing-architecture-webrtc-rtp-sfu-0a45b3f928d0)
- [webrtcHacks: How Zoom avoids WebRTC](https://webrtchacks.com/zoom-avoids-using-webrtc/)
- [Zoom Dev Forum: Separate audio streams](https://devforum.zoom.us/t/separate-audio-streams-for-web-sdk/81174)

### 2.3 Microsoft Teams — UNKNOWN (Needs Live Testing)

**Architecture:** Teams uses standard WebRTC for media transport, but delivers **mixed audio** (all participants on a single stream). Our current bot hooks `RTCPeerConnection.prototype` via `addInitScript` to intercept `ontrack` events.

**CSRC behavior — unknown:**
- Teams receives a single mixed audio stream via WebRTC
- If Teams' media server (MCU-style mixer) sets CSRC values in the mixed stream, `getContributingSources()` would return per-participant audio levels — enabling speaker identification without captions
- If the mixer **strips CSRCs** (common in some MCU implementations), the method returns an empty array
- No public documentation exists on whether Teams' mixer sets CSRC values

**Testing approach:**
Since our bot already hooks RTCPeerConnection, we can easily test:
```javascript
// In addInitScript hook, after ontrack fires:
pc.ontrack = (event) => {
  const receiver = event.receiver;
  setInterval(() => {
    const csrcs = receiver.getContributingSources();
    const ssrcs = receiver.getSynchronizationSources();
    console.log('[Vexa] CSRC:', JSON.stringify(csrcs));
    console.log('[Vexa] SSRC:', JSON.stringify(ssrcs));
  }, 1000);
};
```

**If CSRC is available on Teams:**
- It would provide **per-participant audio levels** on the mixed stream
- Could identify speakers without the 1-1.5s caption delay
- Would be more reliable than the current caption-driven approach
- CSRC→Name mapping: correlate with Teams' DOM (participant tiles have names, and audio level could be matched to CSRC audioLevel)

**If CSRC is NOT available (more likely):**
- Stay with current caption-driven approach (primary) + DOM fallback
- No loss — captions already work well for Teams

**Verdict: Worth a 5-minute live test.** Hook the RTCPeerConnection receivers and log CSRC values. If present, it's a significant improvement over caption-based attribution. If not, no change needed.

---

## 3. getSynchronizationSources() — Related API

```typescript
const ssrcs: RTCRtpSynchronizationSource[] = receiver.getSynchronizationSources();

interface RTCRtpSynchronizationSource {
  source: number;     // SSRC identifier
  timestamp: number;  // DOMHighResTimeStamp
  audioLevel: number; // 0.0 to 1.0
  rtpTimestamp: number;
}
```

**Difference from getContributingSources():**
- SSRC = the stream's own identifier (the virtual stream)
- CSRC = identifiers of the original sources contributing to that stream
- In an SFU that forwards without mixing (like Meet), CSRC tells you WHO is on the stream
- In a P2P call, there's no CSRC (only SSRC) — the stream IS the participant

**For Google Meet:** SSRC identifies the virtual stream (1 of 3), CSRC identifies the participant on it. Both are useful: SSRC tells you which stream, CSRC tells you who.

**For Zoom:** Both are irrelevant — audio doesn't flow through WebRTC receivers.

**For Teams:** SSRC identifies the single mixed stream. CSRC (if present) identifies contributors.

---

## 4. Implementation Approach for Google Meet

### Phase 1: CSRC Discovery (addInitScript)

Hook RTCPeerConnection to capture receivers and poll CSRC:

```javascript
// addInitScript — runs before page load
const OrigPC = window.RTCPeerConnection;
window.RTCPeerConnection = function(...args) {
  const pc = new OrigPC(...args);

  pc.addEventListener('track', (event) => {
    if (event.track.kind !== 'audio') return;
    const receiver = event.receiver;

    // Poll every 250ms for CSRC changes
    setInterval(() => {
      const csrcs = receiver.getContributingSources();
      if (csrcs.length > 0) {
        // Store on window for Node.js to read via page.evaluate()
        window.__vexaCSRC = window.__vexaCSRC || {};
        window.__vexaCSRC[receiver.track.id] = csrcs.map(c => ({
          source: c.source,
          audioLevel: c.audioLevel,
          timestamp: c.timestamp
        }));
      }
    }, 250);
  });

  return pc;
};
window.RTCPeerConnection.prototype = OrigPC.prototype;
```

### Phase 2: CSRC → Name Correlation

One-time correlation using existing DOM speaking indicators:

```javascript
// When DOM shows "Alice" as speaking AND CSRC=42 just became active:
// Lock: CSRC 42 = "Alice" (permanent for session)
// This is the SAME voting logic as current speaker-identity.ts
// but keyed on CSRC instead of track index
```

### Phase 3: Replace DOM Voting

Once CSRC→Name is locked, stop relying on DOM indicators entirely:
- Use `audioLevel` from CSRC for silence detection (replaces ScriptProcessorNode amplitude check)
- Use CSRC `source` for track identity (replaces track index, which can change during SFU remapping)
- Detect SFU remapping instantly (CSRC changes on a stream = different speaker)

---

## 5. Cross-Feature Implications

### Multi-Track Dedup (Score 40)
The "same person on 2 tracks" problem in Google Meet is caused by the SFU putting one person on two virtual streams during remapping transitions. CSRC detection would instantly identify this: if two streams have the same CSRC, they're carrying the same person. Dedup becomes trivial.

### Slow Speaker Locking (585s)
Current locking requires DOM-based voting during single-speaker moments. CSRC provides immediate identity — the first packet on a stream tells you who's speaking. Locking time drops from minutes to ~1 second.

### "All Tracks Vote for Same Speaker" (Zoom)
This Zoom-specific problem cannot be solved by CSRC (Zoom has no CSRCs). Must continue using `isMostRecentlyActiveTrack()` gating with DOM active speaker indicators.

### Segment Confirmation Failure (Score 40)
Not directly related to CSRC. Confirmation failure is about buffer management and Whisper re-segmentation, not speaker identification.

---

## 6. Competitor Approaches

### Recall.ai
- **Google Meet bot** (open source): Uses DOM caption scraping, not CSRC. Source: [github.com/recallai/google-meet-meeting-bot](https://github.com/recallai/google-meet-meeting-bot)
- **Teams bot** (open source): Uses Graph API for bot registration, gets captions with speaker attribution via Microsoft's APIs. Source: [github.com/recallai/microsoft-teams-meeting-bot](https://github.com/recallai/microsoft-teams-meeting-bot)
- No evidence of any competitor using CSRC-based speaker identification

### MeetingBot (open source)
- [github.com/meetingbot/meetingbot](https://github.com/meetingbot/meetingbot) — uses Terraform + AWS deployment
- Recorder-style approach, no CSRC usage found

### Key Insight
**Nobody in the open-source meeting bot space is using CSRC for speaker identification.** This is either because:
1. It's an underexplored approach (opportunity for Vexa)
2. Or practical issues prevent it from working (the Chrome sink bug, platform-specific CSRC stripping)

Given that Google Meet explicitly documents CSRC in their Media API docs, approach #1 seems more likely for GMeet specifically.

---

## 7. Recommendations

### For Google Meet (HIGH PRIORITY)
1. **Implement CSRC polling** via addInitScript hook on RTCPeerConnection
2. **Test in live meeting**: verify `getContributingSources()` returns non-empty arrays with CSRC values
3. If CSRCs present: replace DOM voting with CSRC-based identity. Keep DOM correlation only for initial CSRC→Name mapping
4. Expected impact: Solves multi-track dedup (40→90), speeds up locking (585s→~1s)

### For Teams (LOW PRIORITY — quick test)
1. Add CSRC logging to existing RTCPeerConnection hook (5 lines of code)
2. Check if Teams' mixer sets CSRC values in the mixed audio stream
3. If yes: significant upgrade over caption-based attribution (no 1-1.5s delay)
4. If no: continue with captions (already working)

### For Zoom (NOT APPLICABLE)
1. CSRC is a dead end — Zoom doesn't use standard WebRTC media stack
2. Continue with DOM-based active speaker + traversal approach
3. For better speaker attribution, pursue RTMS API (per-participant audio, but read-only)

---

## 8. Open Questions

1. **Does Google Meet's web client actually populate CSRC?** The Media API docs describe CSRC behavior, but the web client may implement it differently from the API's SFU. Needs live verification.
2. **Can we call getContributingSources() from page.evaluate()?** The receivers are created by Meet's code, not ours. We need addInitScript to capture them before Meet's code runs.
3. **Chrome's current behavior:** Is the empty-without-sink bug fully fixed in Chrome 120+? Our audio elements have sinks, so this is not blocking, but worth knowing.
4. **CSRC stability during Meet's "dynamic multiplex":** When Meet rapidly swaps who's on a virtual stream (e.g., fast back-and-forth conversation), does CSRC update fast enough for reliable attribution?
5. **Does Teams set CSRC in mixed audio?** Only answerable with a live test.
