# Feature Log — Realtime Transcription

Append-only. Records trajectory, decisions, dead ends. Read this before acting — avoid repeating failed approaches.

## Trajectory

| Date | Iteration | Score | Delta | Key change |
|------|-----------|-------|-------|------------|
| 2026-03-20 | Baseline measurement | 18% speaker | — | Discovered comparison was broken; fixed to get accurate baseline |
| 2026-03-20 | Accurate baseline | 24% speaker | — | Carry-forward + shared words + broken comparison = real issues visible |
| 2026-03-20 | Iteration 1 | 88% speaker | +64% | Removed carry-forward, fixed windowStartMs timing, per-speaker words |
| 2026-03-21 | Iteration 2 | 100% speaker | +12% | Mapper boundary merge, stale response guard, context tail trim |
| 2026-03-21 | Iteration 3 (live) | 100% speaker | — | Caption timestamp domain fix, disabled mapper for Teams, retry on 500, latency 16.5s→10.8s |
| 2026-03-21 | Iteration 4 (panel-20) | 95% speaker (7sp) | — | DATASET env var, full speaker name parsing, WS delivery verified |
| 2026-03-22 | Delivery Iteration 1 | 43/43 REST+WS | — | Fixed meeting setup (not collector dedup), inject-and-verify test |
| 2026-03-22 | Delivery Iteration 2 | Single-publisher | — | Collector = persistence only, bot = single WS publisher, dashboard simplified |
| 2026-03-23 | GMeet E2E | 9/9 basic, 18/20 stress | — | Speaker identity voting: 100% TTS accuracy, 15% WER |
| 2026-03-23 | GMeet Human (Meeting 672) | 40 (human speaker) | — | 23/215 unnamed, confirmation failure, multi-track duplication |

## Dead Ends

[DEAD-END] **Carry-forward audio between speakers** — prepending short audio to next speaker's buffer. Causes wrong attribution. Removed entirely in iteration 1 — submit short audio directly to Whisper instead.

[DEAD-END] **Full-text match as primary confirmation** — Whisper output keeps changing slightly as buffer grows, so full-text never matches mid-stream. Replaced with per-segment stability tracking as primary, full-text as fallback.

[DEAD-END] **maxBufferDuration=10 at call site** — overrode the 120s default, forcing hard reset every 10s. Caused scatter in monologues. Set to 120s.

[DEAD-END] **5s idle timeout** — natural speech pauses (2-5s) triggered false idle resets because browser silence filter meant no audio reached Node. Increased to 15s.

[DEAD-END] **Aggressive caption flush on speaker change** — `flushSpeaker()` discarded segments <2s that had no Whisper result yet. Lost 8/18 utterances in run 4. Fixed with min-duration check.

[DEAD-END] **Two WS publishers (bot + collector)** — different formats to same channel. Dashboard couldn't reconcile. Collector removed from WS publish entirely — bot is single publisher.

[DEAD-END] **Mapper for Teams per-speaker audio** — after removing carry-forward, mapper only introduced errors by re-attributing words based on caption boundary timing jitter. Disabled for Teams.

[DEAD-END] **minAudioDuration=0.5s** — introduced garbage segments from silence fragments. Reverted to 3s.

## Platform-Specific Dead Ends

### Google Meet
[DEAD-END] **3-vote threshold for speaker locking** — too slow with overlapping speech. Meeting 672: took 585s to lock speaker-0. Reduced to 2 votes + weighted voting.

[DEAD-END] **Simple mock for E2E testing** — `tests/mock-meeting/index.html` lacks Google Meet DOM structure (no pre-join screen, no toolbar, no participant tiles). Bot gets stuck at "find name input." Must use `features/realtime-transcription/mocks/google-meet.html`.

### MS Teams
[DEAD-END] **Single `lastCaptionSpeaker` with no lookback** — audio arriving between caption changes attributed to wrong speaker. Fixed with 5s ring buffer + retroactive attribution.

## Known Platform Limitations (not bugs)

- **Teams: single-word utterances dropped** — Teams doesn't generate separate caption entries for sub-1s TTS utterances. Platform limitation, not pipeline bug. (5-speaker stress test: 10 short phrases sent, 2 captured)
- **Teams: mixed audio stream** — all speakers in one stream, routed by caption timing. Inherently less accurate than GMeet's per-element streams on fast transitions.
- **GMeet: multi-track duplication** — same participant's audio may appear on multiple `<audio>` elements. Dedup logic needed but not yet implemented.

## Current Blockers (2026-03-23)

1. **GMeet human speaker locking** (score 40) — 8+ minutes to lock is unacceptable. Needs faster voting or alternative identity mechanism.
2. **GMeet confirmation failure on long monologues** — per-segment stability check fails when Whisper returns different segment boundaries each time. Buffer grows unbounded → giant 100-226s monolithic segments.
3. **Multi-track dedup** — same person on multiple audio elements produces duplicate content.
