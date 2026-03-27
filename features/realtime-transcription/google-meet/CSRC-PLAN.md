# CSRC-Based Speaker Identity for Google Meet

**Date:** 2026-03-27
**Goal:** Replace DOM-based speaker detection with `RTCRtpReceiver.getContributingSources()` to fix the 56% empty-speaker-name problem and push speaker identity score from 78 to 90+.

---

## 1. Why the Current Approach Fails

The current speaker identity system (`speaker-identity.ts`) works by:
1. Polling DOM speaking indicators (CSS classes like `.Oaajhc`, `.HX2H7` + `[data-audio-level]`) on participant tiles
2. Correlating which DOM indicator is active when audio arrives on a given track
3. Voting: track N + speaking indicator for "Alice" = vote. After 2 consistent votes, lock permanently.

**Three failure modes cause 56% empty names on speaker-2 track:**

| Failure | Why | Impact |
|---------|-----|--------|
| **SFU stream remapping** | Google Meet SFU multiplexes 3 loudest speakers onto 3 virtual audio streams (SSRCs). When it swaps which participant is on a stream, the track index stays the same but the speaker changes. The current system assumes track=speaker is permanent (`speaker-identity.ts:7-8`: "The mapping never changes"). | Locked mapping becomes wrong after remap. All subsequent segments get wrong name or empty name. |
| **DOM indicator race** | Speaking indicators in the DOM update ~500ms after the audio packet arrives. During fast speaker changes, the indicator for speaker A is still active when speaker B's audio arrives. | Wrong votes → wrong lock, or conflicting votes → never locks. |
| **Multi-track ambiguity** | When >1 person speaks, all 3 tracks may have audio while the DOM shows 2+ speaking indicators. Voting gives fractional weights (`0.5`) but can't determine which track carries which speaker. | Slow or incorrect locking. |

**CSRC solves all three** because the CSRC identifier is embedded in the RTP packet itself — it tells you exactly which participant's audio is on each virtual stream at the packet level, with zero DOM dependency.

---

## 2. How CSRC Works in Google Meet

Google Meet's SFU architecture:
```
Participant Alice (CSRC=42) ──┐
Participant Bob (CSRC=99)  ───┼──→ SFU ──→ Virtual Stream A (SSRC 1) → bot's RTCRtpReceiver[0]
Participant Carol (CSRC=17) ──┘          → Virtual Stream B (SSRC 2) → bot's RTCRtpReceiver[1]
                                         → Virtual Stream C (SSRC 3) → bot's RTCRtpReceiver[2]
```

`RTCRtpReceiver.getContributingSources()` returns:
```typescript
interface RTCRtpContributingSource {
  source: number;       // CSRC — unique per participant, stable for session
  timestamp: number;    // DOMHighResTimeStamp — last frame delivery
  audioLevel: number;   // 0.0–1.0 (linear scale)
  rtpTimestamp: number;
}
```

Key behaviors:
- Returns sources from the **last 10 seconds** only (auto-prunes stale entries)
- `source` (CSRC) is a 32-bit identifier, unique per participant for the session
- When SFU remaps a stream: CSRC changes instantly (not after 500ms like DOM)
- Synchronous call — very cheap to poll (no async/promise overhead)
- Chrome 59+, standard WebRTC 1.0 API

---

## 3. Implementation Plan

### Phase 1: CSRC Capture (addInitScript hook)

**File:** New file `services/vexa-bot/core/src/services/csrc-tracker.ts` (~80 LOC)

Hook `RTCPeerConnection.prototype` before Google Meet loads to intercept audio receivers and poll CSRC:

```typescript
// Injected via page.addInitScript() or page.evaluate() before meet loads
const OrigPC = window.RTCPeerConnection;
window.RTCPeerConnection = function(...args) {
  const pc = new OrigPC(...args);
  pc.addEventListener('track', (event) => {
    if (event.track.kind !== 'audio') return;
    const receiver = event.receiver;
    const trackId = event.track.id;

    setInterval(() => {
      const csrcs = receiver.getContributingSources();
      if (csrcs.length > 0) {
        window.__vexaCSRC = window.__vexaCSRC || {};
        window.__vexaCSRC[trackId] = csrcs.map(c => ({
          source: c.source,
          audioLevel: c.audioLevel,
          timestamp: c.timestamp
        }));
      }
    }, 250);
  });
  return pc;
};
Object.setPrototypeOf(window.RTCPeerConnection, OrigPC);
window.RTCPeerConnection.prototype = OrigPC.prototype;
```

Node.js side reads via `page.evaluate(() => window.__vexaCSRC)`.

**Integration point:** `recording.ts` already runs a large `page.evaluate()` block. The CSRC hook should be injected **before** Meet loads (via `addInitScript` in `join.ts` or `index.ts`), not inside the recording evaluate block.

### Phase 2: CSRC-to-TrackIndex Mapping

**File:** Modify `services/vexa-bot/core/src/index.ts` (`handlePerSpeakerAudioData`, lines ~1437-1570)

Current flow:
```
audio arrives on track N → reportTrackAudio(N) → resolveSpeakerName(page, N, 'googlemeet')
                                                  ↓
                                        queryBrowserState() → DOM speaking indicators → vote → lock
```

New flow:
```
audio arrives on track N → reportTrackAudio(N) → getCSRCForTrack(N)
                                                  ↓
                                        CSRC present? → csrcToName map lookup → instant identity
                                        CSRC absent?  → fall back to DOM voting (existing path)
```

**Challenge:** The current audio pipeline uses `speakerIndex` (0, 1, 2) based on the order `<audio>` elements appear in the DOM. CSRC is keyed by `track.id` (a string). We need to bridge these:

- In the browser: when `createPerSpeakerStreams()` creates a pipeline for element N, also store which `MediaStreamTrack.id` that element carries
- Expose `window.__vexaTrackIdByIndex` mapping: `{ 0: "track-abc123", 1: "track-def456", ... }`
- Node.js reads both `__vexaCSRC` and `__vexaTrackIdByIndex` to resolve: `speakerIndex → trackId → CSRC → name`

### Phase 3: CSRC-to-Name Correlation

**File:** Modify `services/vexa-bot/core/src/services/speaker-identity.ts` (~50 LOC added)

New data structures:
```typescript
/** CSRC → participant name. Once set, permanent for session. */
const csrcToName = new Map<number, string>();

/** Pending CSRC values that need name correlation */
const unmappedCSRCs = new Set<number>();
```

Correlation strategy (one-time per CSRC):
1. When a new CSRC appears, add to `unmappedCSRCs`
2. Query DOM for speaking indicators (same `queryBrowserState()` call)
3. If exactly 1 person speaking AND exactly 1 unmapped CSRC is active → lock: `csrcToName.set(csrc, name)`
4. Once mapped, the CSRC→name binding is permanent for the session (CSRCs don't change per participant)

After initial correlation, CSRC provides instant identity — no more DOM polling needed for that participant.

### Phase 4: SFU Remap Detection

**File:** Modify `services/vexa-bot/core/src/services/speaker-identity.ts`

When CSRC changes on a track (SFU remapped the virtual stream):
1. Detect: `previousCSRC[trackIndex] !== currentCSRC[trackIndex]`
2. If new CSRC is already in `csrcToName` → instant speaker switch, no voting needed
3. If new CSRC is unmapped → trigger correlation (Phase 3)
4. Call `speakerManager.updateSpeakerName()` and flush the previous speaker's buffer

This replaces the current `clearSpeakerNameCache()` approach (lines 1524-1528 in index.ts) which nukes ALL mappings when participant count changes.

### Phase 5: audioLevel-Based Silence Detection

**File:** Modify `services/vexa-bot/core/src/services/audio.ts` (optional, lower priority)

Current silence detection: `ScriptProcessorNode` → check amplitude of PCM samples.

CSRC provides `audioLevel` (0.0–1.0) per source. This could replace the ScriptProcessorNode check, but the existing approach works and this is a marginal improvement. Defer to post-MVP.

---

## 4. Files Changed

| File | Change | LOC |
|------|--------|-----|
| `services/vexa-bot/core/src/services/csrc-tracker.ts` | **NEW** — browser-side CSRC polling script, Node-side reader | ~80 |
| `services/vexa-bot/core/src/platforms/googlemeet/join.ts` | Add `page.addInitScript()` for CSRC hook before navigating to Meet | ~10 |
| `services/vexa-bot/core/src/services/speaker-identity.ts` | Add CSRC→name map, correlation logic, remap detection. Keep DOM voting as fallback. | ~80 |
| `services/vexa-bot/core/src/index.ts` | Modify `handlePerSpeakerAudioData` to try CSRC before DOM voting | ~30 |
| `services/vexa-bot/core/src/platforms/googlemeet/recording.ts` | Store `trackId→elementIndex` mapping in browser for CSRC bridge | ~15 |
| `services/vexa-bot/core/src/services/audio.ts` | In `createPerSpeakerStreams`, expose `track.id` per element | ~10 |

**Total: ~225 LOC new/modified** (plus the existing ~540 LOC in speaker-identity.ts, which gets extended but not rewritten).

---

## 5. Risks and Unknowns

### Critical: Does Google Meet's Web Client Actually Set CSRC?

**Risk level: MEDIUM**

The CSRC research (csrc-speaker-research.md) confirms Google's Meet Media API documentation describes CSRC behavior. However, the web client may implement things differently from the API's SFU path.

**Mitigation:** Phase 1 is pure observation — inject the hook, log CSRC values, don't change any behavior. If `getContributingSources()` returns empty arrays, we know immediately and stop.

**Verification test:**
```javascript
// Add to join.ts addInitScript, observe in bot logs
pc.addEventListener('track', (event) => {
  if (event.track.kind !== 'audio') return;
  setInterval(() => {
    const csrcs = event.receiver.getContributingSources();
    console.log('[Vexa-CSRC]', event.track.id, JSON.stringify(csrcs));
  }, 1000);
});
```

### Medium: Track ID Bridging

The per-speaker audio pipeline (`audio.ts:createPerSpeakerStreams`) currently only knows element index, not track ID. Bridging requires storing the `MediaStreamTrack.id` from `element.srcObject.getAudioTracks()[0].id` when creating each pipeline.

**Risk:** Some elements may have multiple audio tracks, or track IDs may not be stable across the session. Mitigation: fall back to element index if track ID mapping fails.

### Medium: addInitScript Timing

The CSRC hook must run **before** Google Meet creates its RTCPeerConnection. If injected too late, the real PeerConnection is already created without our hook.

**Mitigation:** Use `page.addInitScript()` which injects before any page scripts run. This is the same pattern used in the Teams bot for intercepting `RTCPeerConnection.prototype.ontrack`.

### Low: Chrome Sink Bug

Chrome had a bug where `getContributingSources()` returned empty arrays unless the audio track was attached to a playing `<audio>` element. Now fixed. Our bot already attaches audio to `<audio>` elements (that's how we discover them), so this doesn't affect us even on older Chrome versions.

### Low: CSRC Collisions

CSRC is 32-bit. Collision probability in a meeting with <100 participants is negligible.

### Low: Browser Compatibility

Standard WebRTC 1.0 API. Chrome 59+ (2017). Our bot runs Chromium via Playwright — guaranteed support.

---

## 6. Rollout Strategy

**Phase 1 only (observation)** should ship first. This is zero-risk:
- Inject CSRC hook
- Log CSRC values alongside DOM speaker events
- Compare: does CSRC track identity match DOM-detected identity?
- If yes → proceed to Phases 2-4
- If CSRC is empty → stop, DOM-only approach stays

**Phases 2-4 (CSRC-primary, DOM-fallback):**
- CSRC is the primary identity source when available
- DOM voting becomes fallback for when CSRC is unavailable (participant just joined, correlation not yet done)
- Feature flag: `USE_CSRC_SPEAKER_IDENTITY=true/false` (env var) to toggle

**Phase 5 (audioLevel):** Defer. Marginal improvement, not needed for 90 target.

---

## 7. Expected Impact

| Metric | Current | After CSRC | Why |
|--------|---------|------------|-----|
| Empty speaker names (speaker-2) | 56% | <5% | CSRC identifies speaker per-packet, no DOM race |
| Speaker locking time | 585s worst case | ~1-2s | First CSRC→DOM correlation locks identity |
| Multi-track dedup errors | Common | Rare | Same CSRC on 2 tracks = same person = trivial dedup |
| Overall speaker identity score | 78 | 90+ | Solving all three failure modes |

---

## 8. What This Does NOT Solve

- **Zoom speaker identity:** Zoom doesn't use WebRTC for media. CSRC is a dead end for Zoom. DOM-based approach stays.
- **Teams speaker identity:** Unknown whether Teams sets CSRC in mixed audio. Worth a quick test but not part of this plan.
- **Segment confirmation buffer issues:** Confirmation failures are about Whisper re-segmentation, not speaker identity. Separate problem.
- **Hallucination filtering:** Unrelated to speaker identity.
