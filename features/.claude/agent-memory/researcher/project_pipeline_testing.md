---
name: pipeline_testing_research
description: Meeting AI testing pipeline research — shift-left patterns, tools (webrtcperf, jitsi-meet-torture, Chrome fake devices), competitor approaches, evaluation metrics (WER/DER)
type: project
---

Comprehensive pipeline testing research completed 2026-03-25. Findings at `features/realtime-transcription/tests/pipeline-testing-research.md`.

**Why:** Vexa's testing is mostly at Level 3 (TTS bots in real meetings). Need to shift testing left to cheaper levels for faster iteration.

**How to apply:**
1. Immediate: mock meeting HTML pages per platform + WAV replay harness + WER/DER as CI metrics
2. Chrome `--use-file-for-fake-audio-capture` for browser-level replay at Level 1 cost
3. Nobody has built a mock GMeet/Teams server -- mock HTML pages are the practical alternative
4. Key tools: webrtcperf (OSS, Puppeteer + fake media + tc/netem), jitsi-meet-torture (full test framework), testRTC/Cyara (commercial)
5. Standard datasets: AMI corpus (meetings), VoxConverse (wild), LibriSpeech (ASR), DIHARD (hardest)
6. Dead end: cannot replay WebRTC sessions bit-for-bit (SRTP/DTLS state), only RTP-level replay post-decryption
