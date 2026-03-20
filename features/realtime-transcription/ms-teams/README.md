# MS Teams Realtime Transcription

## Why

Teams provides ONE mixed audio stream for all participants. Unlike Google Meet (which gives per-speaker streams), we can't separate speakers at the audio level. But Teams gives us something Google Meet doesn't: **live captions with perfect speaker attribution**. The architecture uses this: transcribe the mixed stream with Whisper, label segments with caption speaker boundaries.

## What

### Architecture: Transcribe Mixed, Label from Captions

```
                    AUDIO PATH                          CAPTION PATH
                    ==========                          ============
All speakers                                     Teams live captions
     |                                                |
     v                                                v
Single <audio> element                       [data-tid="author"]
     |                                       [data-tid="closed-caption-text"]
     v                                                |
AudioContext(16kHz)                                    v
ScriptProcessor(4096)                          Speaker boundaries:
RMS silence filter (< 0.01)                    "Alice: 0s-12s"
     |                                         "Bob: 12s-18s"
     v                                         "Alice: 18s-25s"
SpeakerStreamManager (1 instance)                     |
     |                                                |
     v                                                v
Whisper (transcribes mixed audio)          Label Whisper output
     |                                     with speaker names
     v
Speaker-attributed segments
```

**Key insight**: we do NOT route audio to per-speaker buffers. That approach (the old architecture) caused cross-speaker contamination, silence dumps, and scattered fragments. Instead, Whisper gets the full mixed stream and captions tell us who said what.

### How Captions Drive Speaker Boundaries

Teams live captions are enabled by the bot after joining (More → Captions). The DOM provides:

```
[data-tid="closed-caption-renderer-wrapper"]     <- container
  └─ [data-tid="author"]                         <- speaker name
  └─ [data-tid="closed-caption-text"]            <- spoken text
```

These are the ONLY stable selectors — Teams renders different container structures for host vs guest views, but `author` and `closed-caption-text` are always present.

**On caption speaker change:**
1. `handleTeamsCaptionData()` detects speaker changed
2. Calls `flushSpeaker(previousSpeakerId)` — emits the previous speaker's buffer as a segment
3. New audio routes to the new speaker's buffer
4. Short segments (< 2s audio) stay in buffer for the speaker's next turn

**On same speaker caption update:**
Audio continues accumulating in the same speaker's buffer. Caption text stored for reconciliation.

### Buffer Management

Uses the offset-based sliding window algorithm (see [parent README](../README.md)):

- `submitBuffer` sends only unprocessed audio (`buffer[timestampOffset:]`)
- Completed Whisper segments advance the offset
- Partial segments re-sent with more context on next submission
- Speaker change flushes the current buffer
- Idle timeout (15s) cleans up when no audio arrives
- Hard cap at 120s

### Caption Enablement

Differs by role:
- **Guest (bot):** More → Captions (direct toggle)
- **Host:** More → Language and speech → Show live captions

The bot handles both paths in `captions.ts`.

### Audio Capture

The RTCPeerConnection hook in `join.ts` intercepts remote audio tracks and mirrors them into hidden `<audio>` elements. `BrowserAudioService` combines these into one stream. A single `ScriptProcessor` processes the mixed audio at 16kHz.

Browser-side silence filter (`RMS < 0.01`) drops quiet chunks before they enter the pipeline. This prevents silence contamination on speaker transitions but means natural speech pauses (2-5s) don't reach the Node-side buffer — which is why idle timeout is set to 15s (not 5s).

### Quality Gate

Short noisy audio causes Whisper hallucinations. The bot checks per-segment signals:
- `no_speech_prob > 0.5 && avg_logprob < -0.7` → noise
- `avg_logprob < -0.8 && duration < 2s` → garbage
- `compression_ratio > 2.4` → repetitive hallucination
- `language_probability < 0.3` → wrong language

### Differences from Google Meet

| Aspect | Google Meet | MS Teams |
|--------|-----------|----------|
| Audio | N per-speaker streams | 1 mixed stream |
| SpeakerStreamManager instances | N (one per channel) | 1 (on mixed stream) |
| Speaker identity | DOM voting/locking | Caption author |
| Diarization | Not needed (pre-separated) | Caption boundaries label output |
| Overlapping speech | Natural (separate streams) | Both speakers in same audio |
| Language | Whisper auto-detects per stream | Whisper auto-detects (captions may be wrong language) |

### Known Limitations

1. **Overlapping speech** — single mixed stream. Both speakers' words appear in the same Whisper output; the caption-active speaker gets attribution.
2. **Caption delay ~1-2s** — speaker transitions within this window may misattribute a few words.
3. **Captions assume one language** — if a speaker switches language, Teams captions produce gibberish. Whisper detects the correct language but the caption text can't be used for reconciliation.
4. **Short interjections** — single words ("Agreed.", "OK.") from a different speaker may be absorbed into the adjacent speaker's segment if the caption change is too brief.

## How

### File Map

| File | Purpose |
|------|---------|
| `recording.ts` | Browser-side: audio queue, silence filter, caption observer, audio routing |
| `captions.ts` | Enable live captions (guest + host paths) |
| `selectors.ts` | DOM selectors. Captions: `[data-tid="author"]` + `[data-tid="closed-caption-text"]` |
| `join.ts` | RTCPeerConnection hook for audio capture, pre-join flow |
| `index.ts` (shared) | `handleTeamsAudioData()`, `handleTeamsCaptionData()`, quality gate |

### Testing

Real live Teams meetings with TTS-speaking bots (Alice, Bob using different user accounts). Test conversation script drives multi-speaker dialogue with normal turns, back-to-back, overlap, and short interjections. Results validated against ground truth input text.

**Test results (2026-03-20):** 5 test runs with progressive fixes. Best run: 16/18 utterances captured correctly, 0 ghost segments, 0 wasted Whisper API calls.
