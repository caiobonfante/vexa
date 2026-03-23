# Speaking Bot Test Findings

## Gate verdict: UNTESTED

## Implementation status (audit 2026-03-23)

Implementation is **code-complete** but never validated end-to-end:
- `services/tts-service/` — Piper TTS, OpenAI-compatible `/v1/audio/speech` endpoint, ONNX voices auto-downloaded from HuggingFace
- `services/vexa-bot/` — plays audio via PulseAudio virtual mic; speak commands handled in index.ts
- `services/bot-manager/` — relays speak commands from API to bot
- `services/api-gateway/` — exposes speak endpoint

TTS service is also used by the realtime-transcription test framework (collection runs use TTS bots), so the service itself is exercised regularly — just not through the speak API path.

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Speak endpoint accepts command | 0 | Route exists in bot-manager | 2026-03-23 (audit) | POST speak command, verify 200 response |
| TTS generates audio | 0 | TTS service works (used by collection runs) | 2026-03-23 (audit) | Verify via speak API path specifically |
| Bot plays audio | 0 | PulseAudio virtual mic code exists | 2026-03-23 (audit) | Verify PulseAudio receives output in container |
| Meeting participants hear bot | 0 | Not tested | — | End-to-end: speak command, audible in meeting |
| Command queuing | 0 | Not tested | — | Send multiple commands, verify sequential playback |

## Risks
- PulseAudio virtual mic setup is container-specific — may not work in all environments
- No voice selection/customization documented in API
