# Feature Log — MS Teams Transcription

Append-only. Records trajectory, decisions, dead ends.

## Trajectory (5 debug runs, 2026-03-20)

| Run | Ghost segs | Lost utterances | Key change |
|-----|-----------|----------------|------------|
| 1 (baseline) | 3 | 5/18 | None — identified infinite idle loop |
| 2 | 0 | 2/18 | Idle fix (`idleSubmitted` flag) |
| 3 | 0 | 0/18 | + silence filter + 3s queue + 2s flush |
| 4 | 0 | 8/18 | + caption speaker flush — TOO AGGRESSIVE |
| 5 | 0 | 2/18 | + skip flush for short segments |

## Dead Ends

[DEAD-END] **maxBufferDuration=10 at call site** — overrode 120s default, forcing hard reset every 10s. Caused scatter in monologues.

[DEAD-END] **5s idle timeout** — natural speech pauses (2-5s) triggered false idle resets because browser silence filter meant no audio reached Node. Increased to 15s.

[DEAD-END] **Aggressive caption flush on speaker change** (run 4) — `flushSpeaker()` discarded segments <2s without Whisper result. Lost 8/18 utterances. Fixed with min-duration check.

[DEAD-END] **Single `lastCaptionSpeaker` with no lookback** — audio between caption changes attributed to wrong speaker. Fixed with 5s ring buffer + retroactive attribution.

[DEAD-END] **Infinite idle resubmit** — `submitBuffer()` reset `lastAudioTimestamp`, preventing idle cleanup. Fixed with `idleSubmitted` flag.

## Results

[RESULT] **Ring buffer + retroactive attribution** — 5s lookback buffer. On caption speaker change, flush lookback audio to previous speaker. Correct attribution on fast transitions.

[RESULT] **Caption-driven routing** — primary speaker source from `[data-tid="author"]` changes. 9-speaker live test: 7/7 speakers correct.

[RESULT] **Silence filter** — RMS < 0.01 threshold + 2s lookback limit + 3s max queue age. Prevents 59-chunk silence contamination on speaker transitions.

## Known Platform Limitations

- **Single-word utterances dropped** — Teams doesn't generate separate caption entries for sub-1s TTS. 10 short phrases sent, 2 captured. Platform limitation.
- **Mixed audio stream** — all speakers in one stream. Less accurate than GMeet's per-element on fast transitions.
- **Caption delay** — 1-2s lag causes wrong attribution on very fast speaker changes.

## Current Stage (2026-03-24)

ITERATE — core pipeline at 90+, delivery at 90+. Ring buffer implemented but untested in live meeting (sandbox only). Next: live Teams meeting with ring buffer to validate.
