# Pipeline Testing Research: Shift-Left for Meeting AI

**Date:** 2026-03-25
**Scope:** How meeting platforms and meeting AI products structure validation from expensive (live meetings) to cheap (unit tests), and what infrastructure exists to support each level.

---

## 1. The Testing Pyramid for Meeting AI

The classic test pyramid (many cheap tests at the base, few expensive tests at the top) maps to meeting AI as follows:

```
                    /\
                   /  \
                  / L4 \     Real live meetings, human speakers
                 /------\    manual verification. Cost: $$$
                /  L3    \   TTS bots in real meetings, known ground truth
               /----------\  Cost: $$
              /    L2       \ Replay: recorded audio through real pipeline
             /--------------\ Cost: $
            /      L1        \ Component tests: mock transcription, mock Redis
           /------------------\ Cost: cents
          /        L0          \ Unit tests: WAV fixtures, JSON in/out
         /----------------------\ Cost: free
```

### Level 0: Unit Tests (Cheapest)
**What:** Deterministic tests with static fixtures. WAV files through STT, JSON through segment processing, speaker-identity voting logic with fixed inputs.
**Catches:** Logic bugs in segment confirmation, speaker voting, buffer management, timestamp math.
**Cannot catch:** Integration failures, audio quality degradation, platform-specific DOM changes, real WebRTC behavior.
**Cost:** Milliseconds, zero infrastructure.
**Used by:** Everyone. Whisper's own eval uses short-form datasets (< 30s clips) with precomputed WER against reference transcripts on LibriSpeech.

### Level 1: Component/Integration Tests (Cheap)
**What:** Mock transcription service (returns canned responses), mock Redis (in-memory), mock WebSocket. Tests the wiring between components without real services.
**Catches:** Protocol mismatches, serialization bugs, missing error handling, Redis stream format issues.
**Cannot catch:** Real service latency, transcription quality, audio capture behavior.
**Cost:** Seconds, Docker containers or mocks.
**Industry pattern:** Microsoft's Bot Framework provides `DialogTestClient` for unit testing bot dialogs in isolation without deployment. Jitsi's `jitsi-meet-torture` tests functional correctness of join/mute/unmute flows.

### Level 2: Replay Tests (Moderate)
**What:** Pre-recorded audio replayed through the real transcription pipeline. No live meeting needed -- audio files are injected into the pipeline at the capture layer.
**Catches:** Transcription accuracy regressions, segment boundary changes, speaker diarization accuracy, pipeline throughput issues.
**Cannot catch:** Browser DOM changes, platform authentication, WebRTC connection issues, real network conditions.
**Cost:** Minutes, requires transcription service running.
**Industry pattern:** SkyScribe treats "transcripts as build artifacts" -- each pipeline run produces a transcript that gets diffed against a baseline. Krisp tests ASR with noise-injected/reverberation-augmented audio files, measuring WER against reference text.

### Level 3: Synthetic Live Tests (Expensive)
**What:** TTS bots speak scripted conversations into real meetings. Ground truth is the script itself. Bot joins via browser, real WebRTC connection, real platform.
**Catches:** Browser compatibility, platform UI changes, WebRTC audio path issues, end-to-end latency, speaker identity resolution from DOM.
**Cannot catch:** Natural speech patterns, accents, crosstalk, real-world network degradation.
**Cost:** Minutes-to-hours, requires platform accounts, cloud compute for browser sessions.
**Industry pattern:** Vexa already does this with TTS bots. Jitsi's `MalleusJitsificus` simulates hundreds of participants with fake media for load testing. testRTC/Cyara runs synthetic WebRTC clients from global locations against production services.

### Level 4: Real Live Tests (Most Expensive)
**What:** Human speakers in real meetings. Manual verification of output.
**Catches:** Everything -- natural speech, accents, crosstalk, real network, real platform behavior.
**Cost:** Human time (the most expensive resource), scheduling overhead.
**Industry pattern:** Used only for final validation. Recall.ai's documentation shows developers test against "a meeting URL (Zoom, Google Meet, or Microsoft Teams)" as a prerequisite, indicating real meetings for integration testing.

---

## 2. How Google and Microsoft Test Internally

### Google's WebRTC Testing Infrastructure

Google does not publish details of internal testing frameworks (ORAT or equivalent), but the public WebRTC project reveals their testing philosophy:

**Chrome's RTP Dump and Replay:**
- Chrome can dump unencrypted RTP packets using `--enable-logging --v=1 --force-fieldtrials=WebRTC-Debugging-RtpDump/Enabled/`
- Packets are captured at the lowest level (before encryption/after decryption) in text2pcap format
- Extraction: `grep RTP_DUMP chrome_debug.log | text2pcap -D -u 1000,2000 -t %H:%M:%S.%f - out.pcap`
- This enables deterministic replay of real sessions without live calls

**libwebrtc Built-in Test Tools:**
- `video_replay` -- replays captured RTP video streams through the WebRTC decoder pipeline. Requires building from source. Outputs frame-by-frame JPEGs or IVF files.
- `neteq_rtpplay` -- the audio equivalent. Simulates NetEq jitter buffer behavior from RTP dumps or PCAP files. Can substitute replacement audio. Outputs aggregated statistics and playback WAV files.
- These tools let Google engineers reproduce specific call quality issues in isolation.

**Fake Device Infrastructure:**
Chrome provides built-in flags for testing without real media devices:
- `--use-fake-device-for-media-stream` -- feeds test pattern to getUserMedia()
- `--use-fake-ui-for-media-stream` -- auto-grants permissions
- `--use-file-for-fake-audio-capture=audio.wav` -- injects specific WAV file as microphone input
- `--use-file-for-fake-video-capture=video.y4m` -- injects specific video file
- Audio loops by default; append `%noloop` to play once

**Google Meet Architecture (public):**
- Uses Opus codec with DTX and in-band FEC
- No P2P even for 2 participants -- always routes through SFU
- Data channels manage stream lifetimes and exchange getStats() every 10s
- Mix-minus audio architecture (each participant gets a unique mix excluding their own audio)

Source: [webrtcHacks - video_replay 2025 update](https://webrtchacks.com/capture-and-replay-streams-with-video-replay/), [WebRTC.org Testing](https://webrtc.github.io/webrtc-org/testing/), [rtcbits.com - Google Meet WebRTC](http://www.rtcbits.com/2022/06/webrtc-google-meet.html)

### Microsoft Teams Testing

Microsoft's approach is more documented for bot developers than for internal testing:

**Bot Framework Emulator:**
- Desktop app for testing bot logic locally without Teams deployment
- `DialogTestClient` class tests dialog flows turn-by-turn in isolation
- Agents Playground (`teamsapptester`) emulates Teams client locally

**Media Bot Testing:**
- ACS (Azure Communication Services) Calling SDK supports local development via ngrok
- Accessing Teams Calling/Meeting APIs for media bots requires special Microsoft permissions
- No public mock Teams meeting server exists

**Network Testing:**
- No published internal tools, but Azure Communication Services documentation suggests using standard tc/netem for network simulation

Source: [Microsoft Learn - Test bots locally](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/debug/locally-with-an-ide), [Microsoft Learn - Unit test bots](https://learn.microsoft.com/en-us/azure/bot-service/unit-test-bots)

---

## 3. Test Data Management

### Ground Truth Creation Strategies

**Strategy A: TTS-generated scripts (deterministic, cheap)**
You write the conversation script, TTS speaks it, you know the exact words. This is what Vexa already does with TTS bots.
- Pros: Perfect ground truth, repeatable, no privacy concerns, scalable
- Cons: TTS speech patterns differ from natural speech, no crosstalk, no accents
- Best for: Regression testing, pipeline validation, CI/CD

**Strategy B: Recorded meetings with manual transcription (expensive, high-value)**
Real meetings with human speakers, manually transcribed afterward.
- Pros: Realistic speech, natural patterns, accents, crosstalk
- Cons: Expensive annotation ($1-2/minute for professional transcription), privacy concerns, non-reproducible
- Best for: Final accuracy validation, benchmark creation

**Strategy C: Synthetic augmentation (moderate cost, good coverage)**
Take clean recordings and augment with:
- Noise injection at varying SNR levels
- Reverberation simulation (room acoustics)
- Audio quality degradation filters
- Speech pace modifications
- Krisp uses this extensively for on-device speech testing
Source: [Krisp - Speech Recognition Testing](https://krisp.ai/blog/speech-recognition-testing/)

**Strategy D: Existing benchmark datasets (free, standardized)**
- AMI Meeting Corpus: 18.7 hours, 4 speakers/session, professional meeting environment, 15.94% overlap speech
- VoxConverse: 63.8 hours from YouTube, 2-20+ speakers, real-world noise
- CALLHOME: Multilingual telephone conversations, 2 speakers
- LibriCSS: Reverberant multi-party conversations
- DIHARD: Most challenging -- meetings, broadcast, clinical, YouTube
- LibriSpeech: Standard for ASR evaluation (used by MLCommons Whisper benchmark)
Source: [Pyannote - How to evaluate diarization](https://www.pyannote.ai/blog/how-to-evaluate-speaker-diarization-performance), [Benchmarking Diarization Models](https://arxiv.org/html/2509.26177v1)

### The Data Pyramid

```
          /\
         /  \   5-10 real meetings with manual transcription (gold standard)
        /----\
       /      \  50-100 recorded meetings with TTS ground truth
      /--------\
     /          \ 500+ augmented audio files (noise, reverb, degradation)
    /------------\
   /              \ 10,000+ unit test fixtures (WAV clips, JSON)
  /----------------\
```

### Replay Infrastructure

**Option 1: Audio file injection at capture layer**
Instead of capturing from browser DOM, inject pre-recorded WAV files directly into the `TranscriptionClient`. This skips the browser entirely.
- Cheapest replay approach
- Tests: transcription service, segment processing, Redis publishing, persistence
- Does NOT test: browser audio capture, speaker identity from DOM

**Option 2: Chrome fake device injection**
Use Playwright with `--use-file-for-fake-audio-capture=audio.wav` to inject audio through Chrome's getUserMedia. The browser thinks it has a real microphone.
- Tests: the full browser pipeline including ScriptProcessor capture
- Does NOT test: real platform DOM, participant join flow
- Limitation: single audio source (cannot simulate multiple participants with separate tracks)

**Option 3: Mock meeting HTML page**
Create a local HTML page that mimics the platform's DOM structure (separate `<audio>` elements per participant, speaking indicators). Load in Playwright.
- Tests: DOM-based audio capture, speaker identity resolution, ScriptProcessor pipeline
- Does NOT test: real platform authentication, WebRTC connection
- This is already in Vexa's certainty table for Zoom ("Mock meeting works" at Level 70)

**Option 4: Local SFU (mediasoup/Janus/Jitsi)**
Run a local WebRTC SFU that creates real WebRTC connections with synthetic participants.
- Tests: real WebRTC connections, codec negotiation, network path
- Complexity: significant setup, but reusable
- mediasoup: best for WebRTC-pure testing, low latency, Node.js native
- Janus: more protocol support, plugin architecture
- Jitsi: full video conferencing, comes with `jitsi-meet-torture` testing framework

Source: [WebRTC SFU Guide](https://www.metered.ca/blog/webrtc-sfu/), [Jitsi Meet Torture](https://github.com/jitsi/jitsi-meet-torture)

---

## 4. Speaker Diarization Testing

### Evaluation Metrics

**DER (Diarization Error Rate):** Sum of missed speech + false alarm + speaker confusion, as percentage of total speech time. Lower is better. State-of-the-art: 5-8% on benchmarks, 15-25% in real-world.

**WDER (Word-level DER):** Evaluates at word boundaries rather than frames. Better reflects transcription quality -- "a speaker confusion during brief hesitation might span several important words."

**JER (Jaccard Error Rate):** Uses intersection-over-union per speaker. Weighs each speaker equally regardless of speaking time. More sensitive to infrequent speakers (important for meetings where some people speak rarely).

### Evaluation Tools
- `pyannote.metrics` -- standard open-source diarization metric computation
- `dscore` -- alternative scoring framework
- Both enforce collar settings (typically 0.25s around boundaries) and overlap handling

### Creating Custom Test Data for Diarization

**Synthetic approach (recommended for regression testing):**
1. Take single-speaker recordings from LibriSpeech or your own TTS
2. Mix them with controlled overlap, gaps, and turn-taking patterns
3. Generate RTTM (Rich Transcription Time Marked) ground truth files automatically
4. Available: `diarizers-community/synthetic-speaker-diarization-dataset` on HuggingFace
5. Academic: "A Free Synthetic Corpus for Speaker Diarization Research" (Springer) -- constructs dialogs from LibriSpeech with 2-3 person dialogs, with and without overlap

**Real data approach (for final validation):**
- AMI corpus is the gold standard for meeting-like environments
- Record your own meetings, manually annotate speaker boundaries
- Use Audacity + RTTM format for annotation

Source: [HuggingFace synthetic-speaker-diarization-dataset](https://huggingface.co/datasets/diarizers-community/synthetic-speaker-diarization-dataset), [Pyannote evaluation blog](https://www.pyannote.ai/blog/how-to-evaluate-speaker-diarization-performance)

---

## 5. Patterns from Meeting AI Companies

### Recall.ai
- Runs "thousands of concurrent VMs every day" for production bots
- Multi-platform testing challenge: "Each platform becomes a separate integration with its own quirks: Zoom's waiting rooms, Google Meet's changing interface elements, Microsoft Teams' breakout rooms"
- For developers using their API: testing against real meeting URLs is the documented approach
- No published testing framework or mock meeting infrastructure
- SOC 2, ISO 27001, GDPR, HIPAA compliant -- implies rigorous testing but details not published
- Their blog "How to build a meeting bot" mentions webhook deduplication testing as critical for production reliability

Source: [Recall.ai - How to build a meeting bot](https://www.recall.ai/blog/how-to-build-a-meeting-bot)

### Otter.ai
- Reports 85-95% transcription accuracy
- Supports domain glossaries for technical vocabulary ("React hooks", "vector DB") -- implies testing with domain-specific vocabularies
- No published engineering blog on testing infrastructure
- Chrome extension approach means testing through browser automation

### Fireflies
- Reports 95%+ transcription accuracy
- "Talk to Fireflies" real-time voice assistant -- implies real-time latency testing requirements
- No published testing methodology

### Krisp (On-device, most transparent about testing)
- Tests three independent components: ASR, punctuation/capitalization, speaker diarization
- Uses WER for ASR, Precision/Recall/F1 for punctuation, DER for diarization
- Data augmentation: noise injection at varying SNR, reverberation simulation, audio quality degradation, speech pace modification
- Combines custom datasets with public benchmarks (Earnings 21)
- Ground truth from linguists manually annotating ASR output
- On-device constraint forces aggressive optimization testing

Source: [Krisp - Speech Recognition Testing](https://krisp.ai/blog/speech-recognition-testing/)

### Key Insight: Nobody publishes their testing infrastructure
Meeting AI companies treat their testing pipeline as competitive advantage. The most detail comes from:
1. Krisp (on-device, so testing methodology is part of their differentiation story)
2. Open-source projects (Jitsi, WebRTC) where testing is public by necessity
3. Infrastructure providers (testRTC/Cyara, webrtcperf) who sell testing tools

---

## 6. WebRTC Testing Infrastructure

### webrtcperf (open source, most relevant tool)
- Spawns multiple Puppeteer headless browsers as synthetic participants
- Injects audio/video via Chrome's fake device flags + FFmpeg
- Network simulation via Linux tc/netem wrapper (bandwidth, latency, packet loss, jitter)
- Can test against real platforms (Google Meet) with automation scripts
- Collects WebRTC PeerConnection statistics, system metrics
- Prometheus/Grafana integration for visualization
- GitHub: [vpalmisano/webrtcperf](https://github.com/vpalmisano/webrtcperf)

### testRTC / Cyara (commercial)
- Simulates real users via automated web browsers from global locations
- Synthetic WebRTC clients check uptime and media quality against SLA
- Active monitoring (scheduled probes) and passive monitoring (real user data)
- Acquired by Cyara -- positions as enterprise WebRTC quality assurance

Source: [Cyara testRTC](https://cyara.com/products/testrtc/)

### Jitsi Meet Torture (open source)
- Full testing framework for Jitsi Meet: functional tests + load tests
- `MalleusJitsificus` simulates hundreds/thousands of synthetic participants
- Tests audio/video muting, active speaker detection, screen sharing
- Uses Selenium + ChromeDriver with fake media devices
- GitHub: [jitsi/jitsi-meet-torture](https://github.com/jitsi/jitsi-meet-torture)

### Loadero (commercial)
- End-to-end WebRTC testing at scale
- Cloud-hosted Selenium/Playwright browsers
- Network condition simulation per participant
- WebRTC-specific metrics collection

Source: [Loadero features](https://loadero.com/features/webrtc/)

### Network Condition Simulation
- Linux `tc`/`netem`: `tc qdisc add dev eth0 root netem delay 200ms loss 10%`
- Can simulate: delay, jitter, packet loss (random and burst), duplication, corruption, reordering
- webrtcperf wraps this via [vpalmisano/throttler](https://github.com/vpalmisano/throttler)
- Critical for testing: bursty packet loss disproportionately affects audio quality. At 1% loss, ~16% of losses are consecutive packets, degrading Opus FEC effectiveness.

Source: [rtcbits.com - Bursty Packet Loss](http://www.rtcbits.com/2024/05/the-impact-of-bursty-packet-loss-on.html), [WebRTC.ventures - Network Simulation](https://webrtc.ventures/2024/06/how-do-you-simulate-unstable-networks-for-testing-live-event-streaming-applications/)

---

## 7. Recommended Pipeline Architecture for Vexa

Based on research, here is the recommended testing pipeline mapped to Vexa's certainty levels:

### Level 0: Unit Tests (WAV fixtures, JSON)
**Cost:** Free. **Time:** Milliseconds. **CI/CD:** Every commit.

| What to test | How | Ground truth |
|---|---|---|
| Segment confirmation logic | Fixed audio buffers, assert segment boundaries | Hardcoded expected outputs |
| Speaker voting/locking | Simulated vote sequences, assert lock at threshold | Expected speaker assignments |
| Buffer management | Edge cases (empty, max size, overflow) | Expected state transitions |
| WER computation | Known transcript pairs | Pre-calculated WER scores |
| Timestamp/offset math | Fixed inputs | Expected outputs |

### Level 1: Component Tests (Mock services)
**Cost:** Cents. **Time:** Seconds. **CI/CD:** Every commit.

| What to test | How | Ground truth |
|---|---|---|
| TranscriptionClient -> service | Mock HTTP server returning canned responses | Expected segment objects |
| SegmentPublisher -> Redis | In-memory Redis mock (or testcontainers) | Expected XADD payloads |
| API Gateway -> client | Mock WS connection | Expected segment delivery |
| Collector -> Postgres | Test database | Expected persisted rows |

### Level 2: Replay Tests (Recorded audio, real pipeline)
**Cost:** Dollars. **Time:** Minutes. **CI/CD:** Daily or per-PR.

| What to test | How | Ground truth |
|---|---|---|
| Transcription accuracy | Inject WAV files at capture layer, run through real transcription service | Reference transcripts, WER threshold |
| Pipeline throughput | Feed multiple audio streams concurrently | Latency measurements |
| Segment confirmation E2E | Recorded audio through full pipeline | Expected confirmed segments |
| Speaker diarization (if applicable) | Multi-speaker WAV through pipeline | RTTM ground truth, DER threshold |

**Key tools:**
- Chrome's `--use-file-for-fake-audio-capture=audio.wav` for browser-level replay
- Direct WAV injection at TranscriptionClient for pipeline-only replay
- Mock meeting HTML page for DOM + audio capture testing

### Level 3: Synthetic Live Tests (TTS bots in real meetings)
**Cost:** $$. **Time:** 5-15 minutes per meeting. **CI/CD:** Weekly or manual trigger.

| What to test | How | Ground truth |
|---|---|---|
| Bot joins meeting via browser | Playwright navigates to real meeting URL | Bot appears in participant list |
| Audio capture from real platform | ScriptProcessor captures from real `<audio>` elements | Non-silent audio arrives |
| Speaker identity from DOM | Real platform DOM with speaking indicators | Correct name assignments |
| End-to-end latency | TTS speaks known phrase, measure time to segment delivery | < 5s speech-to-segment |
| Multi-platform consistency | Same script on GMeet, Teams, Zoom | Same transcript output |

**This is Vexa's current primary testing approach.** The research validates it as Level 3 in a 5-level pyramid -- appropriate for integration validation but expensive for regression testing.

### Level 4: Real Live Tests (Human speakers)
**Cost:** $$$. **Time:** Hours. **Frequency:** Release milestones only.

| What to test | How | Ground truth |
|---|---|---|
| Natural speech accuracy | Real humans in real meetings | Manual transcription review |
| Crosstalk handling | Multiple humans speaking simultaneously | Manual annotation |
| Accent robustness | Speakers with diverse accents | Manual review |
| Long meeting durability | 1+ hour meetings | No crashes, stable memory |

---

## 8. Key Recommendations for Vexa

### Immediate wins (shift expensive tests left):

1. **Create a mock meeting HTML page per platform.** GMeet, Teams, and Zoom each have specific DOM structures for `<audio>` elements and speaking indicators. A mock page with 3-4 fake audio sources and CSS-controlled speaking indicators would move speaker identity testing from Level 3 (real meetings) to Level 1 (local). This is already in the Zoom certainty table as a goal.

2. **Build a WAV replay harness.** Inject recorded meeting audio directly into `TranscriptionClient`, bypassing the browser entirely. This turns transcription accuracy testing from Level 3 to Level 2. Use the AMI corpus or your own TTS-generated conversations as test data.

3. **Adopt WER/DER as CI metrics.** After each pipeline change, compute WER against reference transcripts and DER against speaker ground truth. Fail the build if thresholds regress. Krisp, Whisper's own eval, and MLCommons all use this pattern.

4. **Use Chrome's fake audio for browser-level replay.** Playwright + `--use-file-for-fake-audio-capture=audio.wav` lets you test the full browser audio capture pipeline without a real meeting. Combined with a mock meeting page, this tests ScriptProcessor, AudioContext, and speaker identity at Level 1 cost.

### Medium-term investments:

5. **Build synthetic multi-speaker test datasets.** Mix single-speaker TTS recordings with controlled overlap, gaps, and turn-taking. Generate RTTM ground truth automatically. Use `diarizers-community/synthetic-speaker-diarization-dataset` as a starting point.

6. **Add network degradation tests.** Use tc/netem to simulate packet loss and jitter during Level 3 tests. This catches audio quality issues that only manifest under real network conditions. webrtcperf's throttler module is a ready-made wrapper.

7. **Transcript-as-artifact pattern.** Treat every test run's transcript output as a build artifact. Diff against baselines. Version control reference transcripts. Alert on semantic regressions (keyword recall drops), not just WER changes.

### Long-term infrastructure:

8. **Local SFU for WebRTC testing.** A Jitsi or mediasoup instance as a local "meeting room" where synthetic participants can join, speak, and leave. This would replace real platform meetings for most integration testing, moving Level 3 tests to Level 2 cost.

9. **Continuous monitoring with synthetic probes.** Like testRTC/Cyara, schedule regular synthetic meetings against production to catch platform-side changes (DOM updates, API changes) before users hit them.

---

## 9. Competitor Testing Infrastructure Summary

| Company | Public Testing Info | Approach |
|---|---|---|
| Google (WebRTC) | RTP dump/replay, video_replay, neteq_rtpplay, fake devices, KITE interop testing | Replay + synthetic, extensive automation |
| Microsoft (Teams) | Bot Framework Emulator, DialogTestClient, Agents Playground | Mock clients, no media mocks public |
| Recall.ai | Real meeting testing documented for API users | Black box -- testing infra is competitive advantage |
| Otter.ai | None published | Unknown |
| Fireflies | None published | Unknown |
| Krisp | Detailed: WER/DER metrics, noise augmentation, domain datasets | Most transparent about methodology |
| Jitsi | jitsi-meet-torture, MalleusJitsificus, Selenium + fake media | Open source, full testing framework |
| testRTC/Cyara | Synthetic WebRTC clients, global probe network | Commercial platform |
| webrtcperf | Puppeteer + fake media + tc/netem, open source | Best OSS tool for WebRTC testing |

---

## 10. Dead Ends and Warnings

**[DEAD-END] Mock Google Meet / Teams servers:** Nobody has built a mock of Google Meet or Teams that fully simulates their WebRTC behavior. The platforms are too complex (custom SFU protocols, proprietary signaling). Mock HTML pages that replicate DOM structure are the practical alternative.

**[DEAD-END] Replaying captured WebRTC sessions bit-for-bit:** Chrome's RTP dump captures raw packets, but replaying them requires the exact same session state (SRTP keys, DTLS context). The video_replay and neteq_rtpplay tools work at the RTP level (post-decryption), not as full session replay. You cannot "record and playback" a WebRTC session like you can a WAV file.

**[WARNING] Chrome fake audio has limitations:**
- Single audio source only -- cannot simulate multiple participants with separate tracks
- Audio file is set at browser launch, cannot be changed mid-test
- WAV format: 1 channel, 48 kHz, 16-bit for best compatibility
- Loops by default (append `%noloop` to play once)

**[WARNING] Benchmark DER vs. production DER:** State-of-the-art diarization achieves 5-8% DER on benchmarks but 15-25% in real-world meetings. Do not set CI thresholds based on benchmark numbers.

**[WARNING] Whisper v3 hallucinations:** Whisper large-v3 has increased propensity for hallucinations, manifesting as "long contiguous blocks of consecutive transcription errors." Test explicitly for hallucination (segments with text where there was silence).

---

## Sources

- [webrtcHacks - video_replay 2025 update](https://webrtchacks.com/capture-and-replay-streams-with-video-replay/)
- [WebRTC.org - Testing](https://webrtc.github.io/webrtc-org/testing/)
- [webrtcperf GitHub](https://github.com/vpalmisano/webrtcperf)
- [Jitsi Meet Torture GitHub](https://github.com/jitsi/jitsi-meet-torture)
- [Recall.ai - How to build a meeting bot](https://www.recall.ai/blog/how-to-build-a-meeting-bot)
- [Krisp - Speech Recognition Testing](https://krisp.ai/blog/speech-recognition-testing/)
- [Pyannote - How to evaluate diarization](https://www.pyannote.ai/blog/how-to-evaluate-speaker-diarization-performance)
- [SkyScribe - AI Voice Recognition Testing Pipelines](https://www.sky-scribe.com/en/blog/ai-voice-recognition-testing-pipelines-for-real-calls)
- [Benchmarking Diarization Models (arXiv)](https://arxiv.org/html/2509.26177v1)
- [MLCommons Whisper Benchmark](https://mlcommons.org/2025/09/whisper-inferencev5-1/)
- [Cyara testRTC](https://cyara.com/products/testrtc/)
- [Loadero WebRTC Testing](https://loadero.com/features/webrtc/)
- [rtcbits.com - Google Meet WebRTC](http://www.rtcbits.com/2022/06/webrtc-google-meet.html)
- [rtcbits.com - Bursty Packet Loss](http://www.rtcbits.com/2024/05/the-impact-of-bursty-packet-loss-on.html)
- [WebRTC.ventures - Network Simulation](https://webrtc.ventures/2024/06/how-do-you-simulate-unstable-networks-for-testing-live-event-streaming-applications/)
- [HuggingFace - Synthetic Diarization Dataset](https://huggingface.co/datasets/diarizers-community/synthetic-speaker-diarization-dataset)
- [Microsoft Learn - Test bots locally](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/debug/locally-with-an-ide)
- [Chromium NetEq docs](https://chromium.googlesource.com/external/webrtc/+/master/modules/audio_coding/neteq/g3doc/index.md)
- [Springer - Free Synthetic Corpus for Diarization](https://link.springer.com/chapter/10.1007/978-3-319-99579-3_13)
- [Best Speaker Diarization Models Compared 2026](https://brasstranscripts.com/blog/speaker-diarization-models-comparison)
