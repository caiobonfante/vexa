# Shift-Left Testing Design: Zoom Web Client

**Date:** 2026-03-25
**Purpose:** Move expensive live-meeting tests left to cheap, deterministic local tests. Four approaches ordered by implementation cost, each targeting a different layer of the Zoom pipeline.

---

## 1. Mock HTML Page (Zoom Web Client Fixture)

### What it replaces
Live Zoom meetings for testing: speaker identity resolution (`traverseZoomDOM`, `queryZoomActiveSpeaker`), per-speaker audio capture (`startPerSpeakerAudioCapture`), and ScriptProcessor pipeline wiring.

### DOM structure (matches selectors.ts)

The mock page must replicate Zoom's actual DOM hierarchy. Based on `selectors.ts` and `recording.ts`, these are the critical elements:

```html
<!DOCTYPE html>
<html>
<head><title>Mock Zoom Meeting</title></head>
<body>
  <!-- Meeting app container (selectors.ts:42) -->
  <div class="meeting-app">

    <!-- Footer buttons — signals bot is "in meeting" -->
    <div class="meeting-footer">
      <button aria-label="Leave" class="footer-button-base__button ax-outline footer-button__button">Leave</button>
      <button class="footer-button-base__button ax-outline join-audio-container__btn">Audio</button>
    </div>

    <!-- Layout 1: Normal view — active speaker container (selectors.ts:91) -->
    <div class="speaker-active-container__video-frame" id="active-speaker">
      <div class="video-avatar__avatar">
        <div class="video-avatar__avatar-footer">
          <span>Alice</span>
        </div>
      </div>
    </div>

    <!-- Layout 2: Speaker bar thumbnails (selectors.ts:93) -->
    <div class="speaker-bar-container">
      <div class="speaker-bar-container__video-frame" id="thumb-0">
        <div class="video-avatar__avatar">
          <div class="video-avatar__avatar-footer">
            <span>Alice</span>
          </div>
        </div>
      </div>
      <div class="speaker-bar-container__video-frame" id="thumb-1">
        <div class="video-avatar__avatar">
          <div class="video-avatar__avatar-footer">
            <span>Bob</span>
          </div>
        </div>
      </div>
      <div class="speaker-bar-container__video-frame" id="thumb-2">
        <div class="video-avatar__avatar">
          <div class="video-avatar__avatar-footer">
            <span>Charlie</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Per-participant <audio> elements with fake MediaStreams -->
    <!-- These are what startPerSpeakerAudioCapture() discovers -->
    <audio id="audio-0" autoplay></audio>
    <audio id="audio-1" autoplay></audio>
    <audio id="audio-2" autoplay></audio>
  </div>

  <script>
    // === Fake MediaStream injection ===
    // Create AudioContext per participant, generate non-silent audio
    // that ScriptProcessor can capture (amplitude > 0.005 threshold)

    const SAMPLE_RATE = 48000; // Chrome default for WebRTC
    const participants = ['Alice', 'Bob', 'Charlie'];
    const audioElements = document.querySelectorAll('audio');
    const contexts = [];

    participants.forEach((name, i) => {
      const ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
      const osc = ctx.createOscillator();
      osc.frequency.value = 200 + (i * 100); // Different freq per participant
      osc.type = 'sine';

      const gain = ctx.createGain();
      gain.gain.value = 0; // Start silent — test controls who "speaks"

      const dest = ctx.createMediaStreamDestination();
      osc.connect(gain);
      gain.connect(dest);
      osc.start();

      // Assign the MediaStream to the <audio> element
      audioElements[i].srcObject = dest.stream;
      audioElements[i].play().catch(() => {});

      contexts.push({ ctx, gain, osc, name });
    });

    // === Speaker control API ===
    // Tests call these to simulate speaking/silence

    window.__mockSetSpeaker = (index) => {
      // Mute all, unmute target — simulates one active speaker
      contexts.forEach((c, i) => {
        c.gain.gain.value = (i === index) ? 0.5 : 0;
      });
      // Update active speaker DOM (what recording.ts polls every 250ms)
      const activeContainer = document.getElementById('active-speaker');
      const footer = activeContainer.querySelector('.video-avatar__avatar-footer span');
      footer.textContent = contexts[index].name;
    };

    window.__mockSetSilence = () => {
      contexts.forEach(c => { c.gain.gain.value = 0; });
    };

    // === Screen-share layout toggle ===
    window.__mockScreenShareLayout = () => {
      // Add --active modifier to speaker bar (Layout 2 in selectors.ts)
      document.querySelectorAll('.speaker-bar-container__video-frame').forEach(el => {
        el.classList.remove('speaker-bar-container__video-frame--active');
      });
      const activeIdx = contexts.findIndex(c => c.gain.gain.value > 0);
      if (activeIdx >= 0) {
        document.getElementById(`thumb-${activeIdx}`)
          .classList.add('speaker-bar-container__video-frame--active');
      }
      // Hide normal layout
      document.getElementById('active-speaker').style.display = 'none';
    };
  </script>
</body>
</html>
```

### What this tests (Level 1 cost)

| Component | How | Assertions |
|-----------|-----|------------|
| `startPerSpeakerAudioCapture()` | Discovers 3 `<audio>` elements with MediaStreams | `handleCount === 3` |
| ScriptProcessor pipeline | Oscillator generates non-silent samples | `maxVal > 0.005` in callback |
| `traverseZoomDOM()` | Walks from `<audio>` up to `.video-avatar__avatar-footer` | Returns participant name |
| `queryZoomActiveSpeaker()` | Reads `.speaker-active-container__video-frame` | Returns active speaker name |
| `isMostRecentlyActiveTrack()` | Only track with recent audio votes | Track with `gain > 0` is most recent |
| Speaker voting/locking | After `__mockSetSpeaker(0)` x2, track 0 locks to "Alice" | `getLockedMapping(0) === 'Alice'` |
| Screen-share layout | `__mockScreenShareLayout()` changes DOM | `queryZoomActiveSpeaker` still resolves |

### Key design decisions

1. **Oscillator, not recorded audio.** The mock page needs to generate `MediaStream` objects that Chrome's `AudioContext.createMediaStreamSource()` accepts. Oscillators do this natively. Recorded audio requires `decodeAudioData` + `AudioBufferSourceNode` which adds complexity without testing the capture pipeline differently.

2. **Speaker switching via gain control.** Muting/unmuting oscillators simulates the real Zoom behavior where only the active speaker has non-silent audio. The `maxVal > 0.005` threshold in `startPerSpeakerAudioCapture` naturally gates this.

3. **DOM matches production selectors exactly.** Every CSS class comes from `selectors.ts` verified against live DOM. If Zoom changes their DOM, both the mock and the selectors break — which is the correct failure mode.

### Limitation: `<audio>` elements NOT inside participant tiles

**FINDING from code analysis:** Zoom puts `<audio>` elements in a **separate container** from participant video tiles. The `traverseZoomDOM()` function walks UP from `<audio>` to find `.video-avatar__avatar-footer`, but in real Zoom the audio element's ancestors don't include the video tile. This means Path 1 (DOM traversal) **will always fail** in real Zoom meetings.

The mock page should test BOTH layouts:
- **Layout A (mock-ideal):** `<audio>` inside participant tiles — tests `traverseZoomDOM()` happy path
- **Layout B (production-realistic):** `<audio>` outside tiles — tests that Path 2 (`queryZoomActiveSpeaker` + `isMostRecentlyActiveTrack`) correctly takes over

This is a research finding that should be validated in a live meeting and shared with the implementer.

---

## 2. WAV Replay Harness

### What it replaces
Live meetings for transcription accuracy testing. Inject recorded audio directly into the pipeline, bypassing the browser entirely.

### Architecture

```
                    ┌─────────────┐
  WAV file ───────► │ WAV Reader  │
  (16kHz mono)      └──────┬──────┘
                           │ Float32Array chunks
                           ▼
                ┌──────────────────────┐
                │ handlePerSpeakerAudioData(index, samples) │
                │ or handleTeamsAudioData(name, samples)     │
                └──────────┬──────────┘
                           │
                    ┌──────┴──────┐
                    │ VAD → SpeakerStreamManager → TranscriptionClient │
                    │ → SegmentPublisher → Redis                       │
                    └─────────────┘
```

### Integration with existing `make play-replay`

The existing replay harness in `features/realtime-transcription/tests/` already does WAV injection at the `TranscriptionClient` level. The Zoom harness should reuse this infrastructure:

```typescript
// zoom-replay.ts — thin wrapper around existing replay infrastructure
import { readFileSync } from 'fs';
import { handlePerSpeakerAudioData } from '../../../services/vexa-bot/core/src/index';

// Simulate multi-speaker by playing different WAV files on different track indices
async function replayZoomMeeting(tracks: { wavFile: string; speakerName: string }[]) {
  for (const [index, track] of tracks.entries()) {
    const wav = readWav(track.wavFile); // 16kHz mono Float32
    const CHUNK_SIZE = 4096;

    for (let offset = 0; offset < wav.length; offset += CHUNK_SIZE) {
      const chunk = wav.slice(offset, offset + CHUNK_SIZE);
      // This is the same entry point the browser's ScriptProcessor calls
      await handlePerSpeakerAudioData(index, Array.from(chunk));
      // Simulate real-time pacing (4096 samples at 16kHz = 256ms)
      await sleep(256);
    }
  }
}
```

### What this tests (Level 2 cost)

| Component | Tested | NOT tested |
|-----------|--------|------------|
| VAD silence filtering | Yes | |
| SpeakerStreamManager confirmation | Yes | |
| TranscriptionClient -> Whisper | Yes (real service) | |
| SegmentPublisher -> Redis | Yes | |
| Browser audio capture | | No (bypassed) |
| Speaker identity from DOM | | No (hardcoded names) |
| WebRTC codec effects | | No (raw PCM) |

### Data sources for replay

1. **Existing synthetic audio:** `data/raw/synthetic/long-monologue.wav` (already present)
2. **TTS-generated multi-speaker:** Reuse GMeet/Teams TTS scripts (Alice/Bob/Charlie)
3. **AMI Meeting Corpus:** 18.7 hours of real meeting audio with ground truth (external benchmark)
4. **Recorded Zoom meetings:** Capture via PulseAudio during live testing, archive for replay

### Makefile target

```makefile
# In features/realtime-transcription/tests/Makefile
play-zoom-replay:
	@echo "Replaying Zoom meeting audio through pipeline..."
	npx ts-node zoom-replay.ts \
		--track 0:data/raw/synthetic/alice.wav \
		--track 1:data/raw/synthetic/bob.wav \
		--ground-truth data/raw/synthetic/alice-bob-script.json
```

---

## 3. Chrome `--use-file-for-fake-audio-capture` in Playwright

### What it replaces
Real microphone input when testing the browser-side audio path. Chrome treats a WAV file as if it were microphone input.

### Usage in Playwright context

```typescript
import { chromium } from 'playwright';

const browser = await chromium.launch({
  args: [
    '--use-fake-device-for-media-stream',
    '--use-fake-ui-for-media-stream',
    '--use-file-for-fake-audio-capture=/path/to/test-audio.wav',
    // WAV must be: 1 channel, 16-bit PCM, 48kHz (Chrome's internal WebRTC rate)
    // Loops by default; append %noloop to play once:
    // '--use-file-for-fake-audio-capture=/path/to/test-audio.wav%noloop',
  ],
});
```

### How this applies to Zoom

The Zoom web client **receives** audio from other participants via WebRTC, it doesn't capture it from the microphone. So `--use-file-for-fake-audio-capture` is only useful for:

1. **Voice-agent bots (TTS output):** Bot needs to speak into the meeting. The fake audio capture replaces the microphone, so the bot's TTS output goes through Chrome's getUserMedia -> WebRTC -> other participants hear it.

2. **Self-test loopback:** If the bot both sends (fake capture) and receives (per-speaker elements), you can test the full round-trip. But this requires a real Zoom meeting (or at minimum a local SFU).

### Limitations (critical)

| Limitation | Impact |
|-----------|--------|
| Single audio source | Cannot simulate multiple participants — all "speakers" come from one WAV |
| Set at browser launch | Cannot change audio mid-test (no speaker switching) |
| Only affects getUserMedia | Does NOT populate per-speaker `<audio>` elements (those come from WebRTC) |
| Format requirements | Must be WAV, 1ch, 48kHz, 16-bit PCM |

### Verdict

**Limited utility for Zoom recorder bots.** The recorder bot doesn't use getUserMedia — it captures FROM other participants' audio elements. The fake audio flag is useful for **voice-agent bots** that need to send TTS into the meeting, but does NOT replace the mock HTML page for testing audio capture.

**Recommendation:** Use for MVP3 (TTS bot testing) when bots need to speak. Combine with mock HTML page for capture testing.

---

## 4. webrtcperf (vpalmisano/webrtcperf) Evaluation

### What it is
Open-source tool that spawns multiple Puppeteer/Headless Chrome instances as synthetic WebRTC participants. Collects PeerConnection stats, system metrics, supports network simulation via tc/netem.

### Features relevant to Zoom testing

| Feature | Relevance | Notes |
|---------|-----------|-------|
| Multiple synthetic participants | High | Spawn N headless browsers that join a Zoom meeting URL |
| Fake audio/video injection | High | Uses same `--use-file-for-fake-audio` Chrome flags |
| WebRTC stats collection | Medium | getStats() every N seconds — bitrate, packet loss, jitter |
| Network simulation (tc/netem) | Medium | Test transcription under packet loss / jitter |
| Prometheus/Grafana integration | Low (for now) | Useful at MVP5 for monitoring |
| Custom page scripts | High | Can inject automation scripts for Zoom-specific flows |

### How it would work for Zoom

```yaml
# webrtcperf config for Zoom testing
url: "https://app.zoom.us/wc/MEETING_ID/join?pwd=PASSWORD"
sessions: 3
tabsPerSession: 1
audioFeed: "path/to/tts-alice.wav"
# Custom script to handle Zoom join flow:
customScript: "zoom-join-automation.js"
# Network simulation:
networkProfile:
  downlink: 5000  # kbps
  uplink: 1000
  latency: 50     # ms
  packetLoss: 2   # %
```

### Evaluation

| Criterion | Score | Notes |
|-----------|-------|-------|
| **Ease of setup** | Medium | Requires Node.js, Puppeteer. Docker image available. |
| **Zoom compatibility** | Unknown | Designed for generic WebRTC pages, Jitsi, and custom apps. Zoom's proprietary client may resist automation (CAPTCHA, bot detection). No published Zoom-specific usage. |
| **Value vs mock page** | Low for MVP0-2 | Mock page is simpler and faster for unit/component testing. webrtcperf adds value at MVP3+ when you need multiple real WebRTC participants. |
| **Value vs live meetings** | High for MVP3+ | Cheaper than manual meetings, can run in CI. But still needs a real Zoom account/meeting. |
| **Network simulation** | High | Only tool that provides realistic network degradation testing. tc/netem wrapper is clean. |
| **Stats collection** | High | Automatic getStats() collection helps diagnose audio quality issues. |

### Verdict

**Not needed for MVP0-MVP2.** The mock HTML page + WAV replay harness cover shift-left testing needs at lower cost.

**Valuable at MVP3+** for:
- Load testing: multiple bots joining simultaneously
- Network degradation testing: how does transcription quality degrade under packet loss?
- Regression testing: automated multi-participant scenarios in CI

**Recommendation:** Defer webrtcperf adoption to MVP3. When needed, use its Docker image and write a Zoom-specific automation script (join flow, dismiss popups) based on the existing selectors.ts.

---

## Recommended Implementation Order

```
PHASE 1 (now — unblocks MVP0/MVP1 testing):
  1. Mock HTML page — test speaker identity + audio capture without live meetings
  2. WAV replay harness — test transcription pipeline without browser

PHASE 2 (after MVP2 — unblocks quality iteration):
  3. Chrome fake audio for voice-agent TTS bots
  4. Multi-speaker synthetic datasets (TTS-generated, reuse from GMeet/Teams)

PHASE 3 (after MVP3 — scale and harden):
  5. webrtcperf for multi-participant load testing
  6. Network degradation tests (packet loss, jitter)
```

### Cost/benefit summary

| Approach | Setup cost | Test cost | What it replaces | MVP value |
|----------|-----------|-----------|-----------------|-----------|
| Mock HTML page | 2-3 hours | Milliseconds | Live meeting for speaker identity | MVP0, MVP1 |
| WAV replay harness | 1-2 hours | Seconds | Live meeting for transcription | MVP2 |
| Chrome fake audio | 30 min | Seconds | Real microphone for TTS bots | MVP3 |
| webrtcperf | 4-6 hours | Minutes | Manual multi-participant testing | MVP3+ |

---

## Cross-Feature Findings

### From GMeet (sibling)
- GMeet uses the same `startPerSpeakerAudioCapture()` code path. Any mock HTML page improvements benefit both platforms.
- GMeet's `isDuplicateSpeakerName` dedup (9 scenarios, 100% accuracy) should be tested in the Zoom mock page too — verify `isNameTaken()` prevents duplicate locks.
- GMeet has segment confirmation bugs with long monologues — proactively test this in WAV replay for Zoom.

### From Teams (sibling)
- Teams uses caption-driven speaker identity (different path). Not directly reusable for Zoom.
- Teams' `traverseTeamsDOM()` walks up from audio element — same pattern as `traverseZoomDOM()`. Both likely fail when audio elements are outside participant tiles. The mock page should test this failure mode.

### From pipeline-testing-research.md
- AMI Meeting Corpus (18.7 hours, 4 speakers/session) is the gold standard for replay testing.
- Krisp's noise augmentation approach (SNR injection, reverb) can be applied to WAV replay datasets.
- Nobody in the industry publishes mock meeting pages — this would be novel infrastructure.

---

## Research Finding: `traverseZoomDOM()` Likely Fails in Production

**Hypothesis:** `traverseZoomDOM()` (speaker-identity.ts:344) walks UP from `<audio>` elements to find `.video-avatar__avatar-footer`. In real Zoom web client, `<audio>` elements are placed in a separate container (not inside participant video tiles), so the DOM walk never reaches the name label.

**Evidence:**
1. Recording.ts uses a completely different approach — it polls the active speaker container globally every 250ms, not by walking from audio elements.
2. The selectors.ts comments say "name is in .video-avatar__avatar-footer > span (NOT .video-avatar__avatar-name — that element doesn't exist in Zoom Web Client)" — suggesting DOM structure investigation was done, but the relationship between audio elements and video tiles was not documented.
3. No test or log evidence of `traverseZoomDOM()` ever returning a non-null result.

**Impact:** Path 1 silently fails, Path 2 (`queryZoomActiveSpeaker` + `isMostRecentlyActiveTrack`) must carry all speaker resolution. If Path 2 also fails (e.g., no active speaker during silence), tracks never lock.

**Action:** Validate in a live meeting by adding a log to `traverseZoomDOM()` showing the ancestor chain. If confirmed, either fix the traversal or remove it (dead code) and rely solely on Path 2.
