# Orchestrator Log

## MVP0: 2026-03-24 — Prove the researcher works

**Target:** realtime-transcription/google-meet, score 40 (human speaker locking)
**Team:** single researcher (Opus, read-only + WebSearch)
**Duration:** ~3 minutes

**Result: ROOT CAUSE FOUND for all 3 blockers.**

| Issue | Root cause | Proposed fix | Source |
|-------|-----------|-------------|--------|
| B: Confirmation failure (107-226s monolith segments) | Whisper segment boundaries shift with growing buffer — position-based comparison can never match | Replace per-segment confirmation with word-level prefix comparison (UFAL LocalAgreement) | faster-whisper #456, arxiv 2307.14743 |
| D: Multi-track duplication | Google Meet "3 loudest speakers" SFU remaps audio across elements | Audio fingerprint dedup, or CSRC from WebRTC stats | red5.net blog, Google Meet Media API docs |
| A: Slow speaker locking (585s) | Cascades from D — track remapping prevents consistent voting windows | Solve D first (CSRC or fingerprint), locking becomes instant | — |

**External entries written:** 5 `[EXTERNAL]` entries in `google-meet/tests/feature-log.md` with sources.

**Priority for MVP1:** Fix confirmation logic first (Issue B) — biggest impact, clearest path (UFAL pattern), also fixes playback misalignment (Issue C).

**MVP0 verdict: PASS.** The researcher agent produced actionable findings from the feature artifacts. The self-improvement loop concept works.
