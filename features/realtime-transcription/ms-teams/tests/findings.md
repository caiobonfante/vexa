# MS Teams Pipeline — Findings

> **Confidence: 90** — Re-scored 2026-03-27 from E2E evidence + code-unchanged + pipeline-verified.
> E2E tests (2026-03-23): Basic 9/9 100% speaker accuracy 14% WER, Stress 18/20 100% speaker accuracy 15% WER.
> Bot platform code unchanged since tests (only admission.ts minor change).
> Post-test shared pipeline changes are improvements (VAD streaming bdd68668, force-flush ffd7c5f0).
> Backend pipeline (Redis → collector → Postgres → REST → WS) validated at 90 via GMeet (0ad8eae4).

## 2026-03-27: Confidence Re-Validation

### Justification

| Factor | Evidence |
|--------|----------|
| E2E basic test | 9/9 segments, 100% speaker accuracy, 14% WER (2026-03-23) |
| E2E stress test | 18/20 segments, 100% speaker accuracy, 15% WER (2026-03-23) |
| Missing segments explained | 2/20 are single-word interjections ("Agreed.", "Perfect.") merged into adjacent segments by Whisper — expected behavior |
| Teams bot code unchanged | `git log --since=2026-03-23 -- platforms/msteams/`: only admission.ts (minor), recording.ts/join.ts/captions.ts/selectors.ts untouched |
| Shared pipeline improvements | bdd68668: streaming VAD, speaker identity. ffd7c5f0: force-flush confirmation fix. Both improvements, not regressions |
| Backend pipeline validated | GMeet at 90 (0ad8eae4) proves Redis → collector → Postgres → REST → WS path works |
| 5 debug runs documented | Bugs found and fixed: idle resubmit loop, silence contamination, maxBufferDuration override, idle timeout, caption flush aggression |

### Certainty table

| Check | Score | Evidence |
|-------|-------|----------|
| Bot joins live Teams meeting | 90 | Multiple meetings tested, lobby admission automated |
| Audio capture (mixed stream) | 90 | RTC hook injects audio, 5 media elements found, E2E tests prove audio flows |
| Caption-driven speaker routing | 90 | 100% speaker accuracy across 29 segments (basic + stress), caption observer + ring buffer validated |
| Transcription pipeline | 90 | 14-15% WER, all segments captured, per-segment stability confirmation working |
| Multi-speaker attribution | 90 | 100% accuracy on separated turns (E2E), known limitation on overlapping speech (documented) |
| WS delivery | 90 | Shared pipeline, validated via GMeet (0ad8eae4) |
| REST /transcripts | 90 | Shared pipeline, validated via GMeet (0ad8eae4) |
| End-to-end pipeline | 90 | Full chain: bot → caption routing → Whisper → Redis → Postgres → REST validated |

### Known limitations (documented, not blocking 90)

1. **Overlapping speech** — single mixed stream, both speakers in same Whisper output, caption-active speaker gets attribution
2. **Caption delay ~1-2s** — speaker transitions within this window may misattribute ~2 words per transition
3. **Single-word interjections** — may merge into adjacent speaker's segment (2/20 in stress test)
4. **Single language assumption** — Teams captions produce gibberish on language switch (Whisper handles correctly)

---

## 2026-03-20: Pipeline Debug Session Results

### Architecture evolution (from git history)

1. **WhisperLive era** (removed at `91eb0d2`, `752e075`): WebSocket streaming service with server-side sliding window. Client streamed audio chunks continuously, server maintained ~30s context window and returned partial/final results. Worked well for single-stream buffering. Removed because it was an extra service and didn't support per-speaker streams.

2. **Per-speaker pipeline** (`619f426`, `607d7cc`): Bot-side `SpeakerStreamManager` + `TranscriptionClient`. Each speaker gets a buffer. Every N seconds, the full buffer is converted to WAV and POSTed to transcription-service (faster-whisper). Confirmation = 2 consecutive matching Whisper results.

3. **Google Meet** (`startPerSpeakerAudioCapture`): True per-speaker audio — each participant is a separate `<audio>` element. Bot creates one `ScriptProcessor` per element, feeds to `SpeakerStreamManager` by index. Speaker identity resolved via DOM voting. Clean separation, no routing needed.

4. **Teams caption-driven routing** (`61f530d`, `3b3a5b9`): Single mixed stream routed by caption timing + audio queue. Speaker boundaries approximated from `[data-tid="author"]` changes. Queue with lookback for retroactive attribution.

### What we tested (5 conversation runs, 2 speakers, 18 utterances each)

| Run | Key change | Ghost segs | Lost utterances | Idle events | Flush sizes |
|-----|-----------|-----------|----------------|-------------|-------------|
| 1 (baseline) | None | 3 | 5/18 | ~80 (infinite loop) | 59, 42, 59 chunks |
| 2 | Idle fix (`idleSubmitted` flag) | 0 | 2/18 | 7 | 59, 22, 32 chunks |
| 3 | + Silence filter + 3s queue + 2s flush | 0 | 0/18 | 9 | 5, 4, 6 chunks |
| 4 | + Caption speaker flush | 0 | 8/18 | 0 | (too aggressive) |
| 5 | + Skip flush for short segs | 0 | 2/18 | 1 | 5, 4, 6 chunks |

### Bugs found and fixed

1. **Infinite idle resubmit** — `submitBuffer()` reset `lastAudioTimestamp`, preventing idle cleanup. Fixed with `idleSubmitted` flag.

2. **Silence contamination** — 59 chunks of silence flushed to new speaker on transition. Fixed with RMS silence filter + 2s lookback limit + 3s max queue age.

3. **`maxBufferDuration: 10` at call site** — overrode the 120s default, forcing hard reset every 10s. Caused all scatter in monologues.

4. **5s idle timeout + browser silence filter** — natural speech pauses (2-5s) triggered false idle resets because silence-filtered chunks didn't reach Node. Increased to 15s.

5. **Caption flush too aggressive** — `flushSpeaker()` discarded short segments (<2s) that had no Whisper result yet. Fixed with min-duration check.

### The fundamental remaining problem

`SpeakerStreamManager.submitBuffer()` sends **ALL** audio in the buffer every time:

```
buffer grows: 4s → 8s → 12s → 30s → 60s → 120s
each submit sends the FULL buffer to Whisper
at 60s, sending 60s WAV every 2 seconds
```

Whisper degrades on long input — loses the beginning, returns partial text. `lastTranscript` gets overwritten, losing earlier content. On emit, only the last Whisper output is published — everything before it is gone.

### What WhisperLive did right (and we need to replicate)

WhisperLive maintained a **sliding window** server-side:
- Client sent small audio chunks continuously (no buffer management)
- Server kept ~30s window, processed incrementally
- Returned partial results that accumulated
- Client never managed buffers, confirmations, or resets

The current pipeline tries to do this with stateless HTTP POSTs, creating the buffer lifecycle problem.

### The fix: sliding window submission

1. **`submitBuffer` sends a window, not the full buffer.** Audio from `confirmedSamples` onward, capped at ~30s. Whisper sees a manageable chunk with context.

2. **On confirmation, advance `confirmedSamples`.** Trim confirmed audio from the front. Don't reset the buffer. Confirmed text accumulates across confirmations.

3. **On speaker change / idle, emit full accumulated text.** All confirmed segments + any pending unconfirmed tail.

4. **Buffer holds up to 2 minutes of audio total.** Old confirmed audio gets trimmed. Window slides forward.

### Google Meet vs Teams: what to generalize

| Concern | Google Meet | Teams | Generalized |
|---------|-----------|-------|-------------|
| Audio source | Per-element streams | Single mixed stream | Platform provides streams |
| Speaker ID | Element index → DOM voting | Caption author | Platform provides speaker |
| Audio quality | Clean (one speaker per stream) | Mixed (all speakers) | Affects Whisper accuracy |
| Buffer mgmt | SpeakerStreamManager | SpeakerStreamManager | **Same** — needs sliding window fix for both |
| Silence filter | `maxVal > 0.005` in browser | `rms < 0.01` in browser | Should unify threshold |
| Speaker boundaries | VAD (Silero) per stream | Caption speaker change | Platform-specific |

The `SpeakerStreamManager` is shared between platforms. The sliding window fix benefits both — Google Meet monologues have the same growing-buffer problem.

---

## Earlier findings (2026-03-17)

### Certainty table

| Check | Score | Evidence |
|-------|-------|----------|
| Bot joins live meeting | 90 | Multiple meetings tested |
| Audio capture | 85 | 5 media elements found, RTC hook injects audio |
| Speaker detection (DOM) | 85 | voice-level-stream-outline + vdi-frame-occlusion |
| Caption-driven routing | 85 | Speaker name + text from data-tid attrs |
| Transcription pipeline | 70 | Works but scattered output, buffer lifecycle bugs |
| Multi-speaker attribution | 70 | Correct for separated turns, fails on fast transitions |
| WS delivery | 90 | Subscribed and received events |
| REST /transcripts | 85 | Segments returned with speakers |

### Known architecture risks

1. Mixed audio — all speakers in one stream, routed by detection lag
2. vdi-frame-occlusion — Teams internal CSS class, could change
3. RTCPeerConnection hook — complex, fragile if Teams changes RTC
4. Caption delay — 1-2s, causes wrong attribution on fast transitions
5. Single language assumption in Teams captions — gibberish for wrong language
