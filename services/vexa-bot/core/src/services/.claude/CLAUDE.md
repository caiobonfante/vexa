# Bot Services Agent

> Shared protocol: [agents.md](../../../../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
Bot internal services: audio capture, speaker identity, VAD, transcription client, segment publisher, recording, chat, screen content, hallucination filter, TTS.

## What you know
- audio.ts: per-speaker AudioContext pipelines — ScriptProcessorNode → resample → Float32 PCM. SpeakerStreamHandle per media element.
- speaker-identity.ts: track→speaker voting (LOCK_THRESHOLD=3, LOCK_RATIO=0.7). One-name-per-track, one-track-per-name enforced.
- speaker-streams.ts: confirmation buffer — accumulate audio, resubmit every interval, emit only when transcript beginning stabilizes. Hard cap force-flush.
- transcription-client.ts: HTTP POST to transcription-service with retries (default 3, 1s backoff).
- segment-publisher.ts: Redis XADD to transcription_segments stream + PUBLISH speaker events. Segments have segment_id = {session_uid}:{speakerId}:{seq}.
- vad.ts: Silero ONNX model via onnxruntime-node. Speech/silence binary filter.
- recording.ts: WAV file accumulation in /tmp, upload via HTTP. No retry on upload failure — silent loss.
- chat.ts: MutationObserver for chat messages, Redis storage. Can inject chat into transcription stream.
- hallucination-filter.ts: phrase files from hallucinations/*.txt + repetition detection. Multi-path resolution (dist/src/Docker).

### Gate (local)
Audio buffer flows from browser MediaStream through VAD to transcription client HTTP POST. PASS: audio.ts captures samples, VAD filters silence, transcription-client POSTs to endpoint. FAIL: AudioContext errors, VAD model fails to load, or HTTP POST never fires.

### Docs
No docs pages. Docs gate: README → code and code → README only.

## Critical questions
- Does recording upload have retry now? (known gap — silent loss on failure)
- Is VAD model file (silero_vad.onnx) present and loadable?
- Are hallucination phrase files found at runtime? (path resolution across dist/src/Docker)
- Does confirmation buffer actually advance? (or does it hit hard cap every time?)

## After every run
Update with buffer behavior observations, upload success rates, VAD load status.

