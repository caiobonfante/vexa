# Zoom Speaker Attribution Research

**Date:** 2026-03-25
**Scope:** How to get per-speaker audio/attribution in Zoom meetings for transcription bots

---

## 1. Zoom Web Client Audio Architecture

Zoom's web client does **NOT** use standard WebRTC for media. It historically used WebRTC DataChannels only, with a custom media stack. Key implications:

- **No separate RTCPeerConnection per participant** -- Zoom handles media multiplexing server-side
- **No raw audio access via Web SDK** -- the Zoom Web SDK does not expose raw audio/video data to developers
- **`mediaCapture` API only triggers recording consent popup** -- does not give actual stream access
- **Only Windows/Linux/macOS native Meeting SDKs** can access raw audio data in real-time

**Bottom line:** A browser-based Zoom bot cannot get per-participant audio through the Web SDK. The audio arrives as a mixed stream.

Sources:
- [Separate audio streams for Web SDK - Zoom Forum](https://devforum.zoom.us/t/separate-audio-streams-for-web-sdk/81174)
- [How to access raw audio stream - Zoom Forum](https://devforum.zoom.us/t/how-to-access-raw-audio-stream/70415)
- [Recall.ai: Can I access raw audio data using the Zoom Web SDK?](https://www.recall.ai/blog/can-i-access-raw-audio-data-using-the-zoom-web-sdk)
- [How Zoom's web client avoids using WebRTC](https://webrtchacks.com/zoom-avoids-using-webrtc/)

---

## 2. Zoom RTMS (Realtime Media Streams)

Zoom's official API for streaming meeting media. Launched 2025, now GA.

### What RTMS provides
- Per-participant audio, video, and transcripts via WebSocket
- Speaker-separated audio channels (`AUDIO_MULTI_STREAMS` mode)
- `onActiveSpeakerEvent` callback for speaker identification
- Live transcripts with speaker attribution and timestamps
- Low-latency, no bot in the meeting

### Audio format options
| Mode | Codec | Sample Rate | Channels | Speaker ID |
|------|-------|-------------|----------|------------|
| AUDIO_MULTI_STREAMS | OPUS/L16 | 48kHz/16kHz | Stereo/Mono | Per-participant |
| AUDIO_MIXED_STREAM | OPUS/L16 | 48kHz/16kHz | Mono | None (use onActiveSpeakerEvent) |

### Critical limitations
- **No bidirectional communication** -- cannot speak, chat, or interact in the meeting (read-only)
- **Host approval required** -- host must approve RTMS connection per-meeting
- **All-or-nothing data requests** -- if host denies any requested media type, ALL are denied
- **No breakout room support** -- streaming stops during breakout sessions
- **Org admin must enable** -- requires Zoom admin to enable RTMS for the org
- **Minimum Zoom client version required** for participants

### Implication for Vexa
RTMS is ideal for passive transcription with perfect speaker attribution. But since Vexa bots need to **speak, chat, and share screen** in meetings, RTMS alone is insufficient. We need a bot-based approach for bidirectional interaction, with RTMS as a possible supplementary audio source.

Sources:
- [Zoom RTMS Developer Docs](https://developers.zoom.us/docs/rtms/)
- [Understanding Zoom RTMS Behavior and Constraints - Recall.ai](https://www.recall.ai/blog/understanding-zoom-rtms-behavior-and-its-constraints)
- [What is Zoom RTMS? - Recall.ai](https://www.recall.ai/blog/what-is-zoom-rtms)
- [Zoom RTMS SDK - GitHub](https://github.com/zoom/rtms)

---

## 3. How Recall.ai Handles Zoom Speaker Attribution

Recall.ai offers two approaches for Zoom:

### Bot-based (traditional)
- Bot joins the meeting as a participant
- Provides **separate per-participant audio streams** for accurate transcription
- Typical latency 200-500ms
- Full bidirectional capability (speak, chat, share)

### RTMS-based (Meeting Direct Connect)
- No visible bot in meeting
- Per-participant audio via RTMS WebSocket
- Speaker attribution from RTMS transcripts (includes speaker-change events)
- **Read-only** -- cannot interact with meeting

### Key insight
Recall.ai recommends RTMS for passive recording/transcription and bots for interactive use cases. Their bot-based approach explicitly provides per-participant audio, suggesting they capture separate audio tracks from each participant via the native Zoom SDK (not the web client).

Sources:
- [Recall.ai Zoom RTMS docs](https://docs.recall.ai/docs/meeting-direct-connect-for-zoom-rtms)
- [Zoom Overview - Recall.ai](https://docs.recall.ai/docs/zoom-overview)

---

## 4. Mixed Audio Speaker Diarization (When Per-Speaker Audio Is Unavailable)

When the bot can only capture mixed audio (as with browser-based Zoom bots), speaker diarization is required post-hoc. Three main approaches:

### A. Pyannote + Whisper (recommended pipeline)

**How it works:**
1. Pyannote segments audio by speaker (produces time intervals labeled SPEAKER_0, SPEAKER_1, etc.)
2. Whisper transcribes the full audio with timestamps
3. Segments are matched by temporal overlap -- each Whisper segment gets the speaker label with the most overlap

**pyannote-audio 4.0 + community-1** (latest):
- Open-source diarization model
- "Exclusive speaker diarization" feature simplifies reconciliation with transcription timestamps
- Requires HuggingFace token + model agreement

**Accuracy:** Good for non-overlapping speech. Struggles with:
- Simultaneous speakers (crosstalk)
- Very short utterances
- Similar-sounding voices

### B. WhisperX (integrated solution)

- 70x realtime transcription with large-v2
- Built-in word-level timestamps via wav2vec2 alignment
- Built-in speaker diarization via pyannote
- Single pipeline: audio in -> speaker-attributed transcript out
- **Not designed for real-time streaming** -- batch processing, 380-520ms latency in optimized setups

### C. whisper-diarization (MahmoudAshraf97)

1. Extract vocals (remove background noise) to improve speaker embedding accuracy
2. Transcribe with Whisper
3. Align timestamps with ctc-forced-aligner
4. Diarize with pyannote
5. Match segments

**Best for:** Post-meeting processing of recorded audio. Not suitable for real-time.

Sources:
- [WhisperX - GitHub](https://github.com/m-bain/whisperX)
- [whisper-diarization - GitHub](https://github.com/MahmoudAshraf97/whisper-diarization)
- [Pyannote speaker-diarization-3.1 - HuggingFace](https://huggingface.co/pyannote/speaker-diarization-3.1)
- [Whisper + Pyannote guide](https://scalastic.io/en/whisper-pyannote-ultimate-speech-transcription/)
- [Pyannote community-1](https://www.pyannote.ai/blog/community-1)

---

## 5. Approaches for Vexa's Zoom Bot

Given that Vexa bots are browser-based and need bidirectional interaction, here are the options ranked by feasibility:

### Option A: Browser bot + mixed audio + diarization (most feasible now)

**How:** Capture mixed audio from Zoom web client (system audio or WebAudio API), run diarization post-hoc.

| Pros | Cons |
|------|------|
| Works with existing browser bot architecture | No real-time per-speaker attribution |
| No Zoom API approval needed | Diarization accuracy degrades with crosstalk |
| Full bidirectional capability | Requires GPU for pyannote/WhisperX |

**Speaker name mapping:** Use Zoom's active speaker indicator in the DOM (CSS class changes on participant tiles) to correlate speaker identity with audio timing. This gives name-to-speaker-cluster mapping.

### Option B: Browser bot for interaction + RTMS for audio (hybrid)

**How:** Bot joins for speaking/chatting/screen-sharing. RTMS provides per-participant audio separately.

| Pros | Cons |
|------|------|
| Perfect speaker attribution from RTMS | Requires Zoom Marketplace app approval |
| Bot still provides interaction | Host must approve RTMS each meeting |
| Real-time speaker-attributed transcripts | Two separate systems to maintain |
| | Org admin must enable RTMS |

### Option C: Native Zoom SDK bot (long-term)

**How:** Use Zoom Meeting SDK (Linux headless) instead of browser, get raw per-participant audio.

| Pros | Cons |
|------|------|
| Per-participant raw audio | Major architecture change |
| No diarization needed | Zoom SDK licensing/approval |
| Lower latency | Different from Teams/Meet approach |

### Recommendation

**Short-term (now):** Option A -- mixed audio + active speaker DOM monitoring for real-time hints, post-meeting diarization with pyannote for final attribution. This requires no external approvals and works with current architecture.

**Medium-term:** Option B -- apply for Zoom RTMS access. Once approved, use RTMS for audio/transcription while keeping browser bot for interaction.

**Long-term:** Evaluate Option C only if RTMS constraints become blocking.

---

## 6. Active Speaker DOM Approach (Browser Bot Specific)

The browser-based approach has one unique advantage: the Zoom web client **visually indicates the active speaker** in the DOM. This can be used for real-time speaker attribution without diarization:

1. Monitor DOM for active speaker CSS class changes on participant tiles
2. Correlate with audio timing to attribute segments
3. Map participant display names to speaker clusters

**Limitations:**
- Only shows ONE active speaker at a time (misses simultaneous speakers)
- DOM updates may lag actual speech by ~500ms
- Requires robust DOM selectors that survive Zoom UI updates

This approach is already being explored in task #18 (Zoom web client audio architecture research).
