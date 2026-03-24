# Feature Log — Zoom Transcription

Append-only.

## 2026-03-23

[STATUS] Scaffold only. No code, no tests, no data. All certainty scores at 0.

[DECISION] Browser-based approach chosen over legacy SDK. Rationale: aligns all 3 platforms on same codebase (ScriptProcessor audio capture, speaker identity voting, same SpeakerStreamManager). Legacy SDK at `services/vexa-bot/core/src/platforms/zoom/` requires proprietary binaries and separate code path.

[RESEARCH] Zoom web client DOM structure unknown. Needs live inspection at `zoom.us/wc/join/{id}`. Open questions: per-participant audio elements or mixed? Speaking indicator selectors? CAPTCHA/anti-bot on join? Waiting room behavior?

## Current Stage

ENV SETUP — need to inspect Zoom web client DOM before any implementation. First step: spawn browser session, navigate to `zoom.us/wc/join/{test-id}`, document DOM structure.
