---
name: Google Meet Audio Architecture Research
description: Deep research on Google Meet WebRTC architecture, 3 virtual audio streams, CSRC-based speaker ID, Meet Media API status, competitor approaches — as of March 2026
type: project
---

Google Meet uses 3 virtual audio streams via SFU (not per-participant streams). The 3 loudest speakers are dynamically multiplexed across 3 SSRCs. CSRC identifiers in RTP headers identify true source per participant.

**Why:** The team needs to understand GMeet audio architecture for browser-bot-based real-time transcription. The 3-stream limit affects speaker identification strategy.

**How to apply:**
- Current ScriptProcessorNode per-element approach works but captures multiplexed streams, not true per-speaker audio
- CSRC-based speaker ID via RTCRtpReceiver.getContributingSources() is a more robust alternative to DOM class scraping
- Meet Media API is Developer Preview only (requires ALL participants enrolled) — not production-viable as of March 2026
- Fireflies uses Meet Media API with apparent special access; Recall.ai uses browser bot + caption scraping (open source)
- `[data-audio-level]` selector is more stable than obfuscated CSS classes for speaking detection
- ScriptProcessorNode deprecated but still works; AudioWorklet migration via Blob URL is the fallback plan

Full research at: features/realtime-transcription/google-meet/tests/gmeet-realtime-research.md
