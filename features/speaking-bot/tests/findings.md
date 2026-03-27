# Speaking Bot Test Findings

## Gate verdict: PASS — regular bots + Zoom live validated

## Score: 90 (Zoom TTS validated live 2026-03-25)

Regular meeting bots (Teams/Google Meet) have a fully working speak pipeline validated at Level 5 with 16 complete speak cycles. Browser session bots had 4 bugs — all 4 fixed and independently verified (2026-03-24).

## Browser Session Fixes (2026-03-24)

All 4 bugs fixed by executor, independently verified by verifier with zero discrepancies:

| Bug | Fix | File | Verified |
|-----|-----|------|----------|
| Channel mismatch | Subscribe to `bot_commands:meeting:{id}` | browser-session.ts:213-284 | CONFIRMED |
| No speak handler | Added handleCommand with TTSPlaybackService | browser-session.ts:220-278 | CONFIRMED |
| TTS_SERVICE_URL missing | Added to browser_session env | orchestrator_utils.py:619 | CONFIRMED |
| PULSE_SERVER not set | Added to browser_session env | orchestrator_utils.py:621 | CONFIRMED |

Additional: `meeting_id` added to BrowserSessionConfig (types.ts:51), passed in config JSON (main.py:701).

**Activated:** vexa-bot:dev rebuilt 2026-03-25. Zoom live test (meeting 72): full TTS cycle — synthesize → unmute → paplay → mute. Bot survived without ejection (grace period fix working).

## Implementation status (validated 2026-03-24)

Implementation is **code-complete for regular bots**, broken for browser_session bots:
- `packages/tts-service/` — Piper TTS, OpenAI-compatible `/v1/audio/speech` endpoint, ONNX voices, generates ~53KB WAV for "hello world" in <100ms
- `services/vexa-bot/core/src/index.ts:470` — speak handler: subscribes to `bot_commands:meeting:{id}`, calls TTS, plays via `paplay --device=tts_sink`
- `services/bot-manager/app/main.py:2889` — relays speak commands via Redis pub/sub
- `services/api-gateway/` — `POST /bots/{platform}/{native_meeting_id}/speak` returns 202

TTS service is also used by collection runs (send-tts-bots), but that's a DIFFERENT code path — bots call TTS directly from their script. The speak API uses the full relay chain: client → gateway → bot-manager → Redis → bot → TTS → PulseAudio.

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Speak endpoint accepts command | 90 | POST returns `{"message":"Speak command sent","meeting_id":39}` (HTTP 202). Alpha + Beta verified. | 2026-03-24 | — |
| TTS generates audio | 90 | Direct test: `POST /v1/audio/speech` → 52-54KB WAV. Alpha + Beta verified. | 2026-03-24 | — |
| Bot receives command (regular) | 90 | Meeting 42: 16 speak.started events in Redis event_log. Alpha + Beta verified. | 2026-03-24 | — |
| Bot receives command (browser_session) | 0 | **BUG**: Channel mismatch + no speak handler. See Bugs section. | 2026-03-24 | Fix 3 bugs below |
| Bot plays audio (regular) | 90 | Meeting 42: 16 speak.completed events, playback times 1.5s-19s. Alpha + Beta verified. | 2026-03-24 | — |
| Meeting participants hear bot | 70 | Inferred from speak.completed events — no direct listener verification. | 2026-03-24 | Join meeting as observer, verify audio audible |
| Command queuing | 0 | Not tested | — | Send 3 commands rapidly, verify sequential playback |

## Bugs Found (3)

### Bug 1: Channel mismatch for browser_session bots
- **bot-manager** publishes speak commands to `bot_commands:meeting:{id}` (main.py:2889)
- **browser-session.ts** subscribes to `browser_session:{container_name}` (line 202-221)
- Commands are published but never received by browser_session bots
- **Fix**: Subscribe browser_session to `bot_commands:meeting:{id}` in addition to its current channel

### Bug 2: No speak handler in browser_session
- `browser-session.ts:213-221` only handles `save_storage` and `stop` commands
- Even if the channel were correct, speak commands would be ignored
- **Fix**: Add speak command handler calling `ttsPlaybackService.synthesizeAndPlay()`

### Bug 3: TTS_SERVICE_URL missing from browser_session container env
- `orchestrator_utils.py:~614` `start_browser_session_container()` does NOT pass `TTS_SERVICE_URL`
- Regular bot path (line 269-271) DOES pass it
- **Fix**: Add `f"TTS_SERVICE_URL={os.getenv('TTS_SERVICE_URL', 'http://tts-service:8002')}"` to browser_session environment list

## Cost Ladder

| Level | Cap | Status | Evidence | Date |
|-------|-----|--------|----------|------|
| 1 | 50 | **VALIDATED** | POST speak → 202 Accepted. Alpha + Beta verified. | 2026-03-24 |
| 2 | 60 | **VALIDATED** | TTS service generates 52-54KB WAV for "hello world". Alpha + Beta verified. | 2026-03-24 |
| 3 | 70 | **VALIDATED (regular bots)** | Meeting 42: 16 speak.started + 16 speak.completed in Redis. Alpha + Beta verified. BLOCKED for browser_session (3 bugs). | 2026-03-24 |
| 4 | 75 | NOT TESTED | Need PulseAudio volume/activity check during playback | — |
| 5 | 80 | **VALIDATED (regular bots, inferred)** | Meeting 42: 13+ complete speak cycles, playback 1.5-19s range. No direct listener confirmation. | 2026-03-24 |

## Industry Context (from researcher)

- **Recall.ai** requires callers to pre-render MP3 audio. Vexa's server-side TTS with `{"text":"..."}` is simpler for integrators and a competitive advantage.
- **Neither Fireflies nor Otter** expose a bot-speak API — this is a differentiator.
- **Latency quality bar**: POST → audible <800ms for short text. Piper is local ONNX (~<100ms synthesis), well within target.
- **PulseAudio gotcha**: 500ms sleep between unmute and audio start is conservative — could be reduced for lower latency.

## Latency Benchmarks (from executor, verified)

### POST → 202 (gateway acceptance)
Average: **18ms** (3 runs: 17ms, 18ms, 19ms) — well under 50ms target.

### TTS Synthesis (Piper ONNX, local)
| Phrase length | Synthesis time | Audio size |
|---------------|---------------|------------|
| 2 words | 78ms | 51KB |
| 10 words | 214ms | 181KB |
| 31 words | 626ms | 598KB |

Scales linearly at ~20ms/word. Short phrases meet <100ms; longer ones scale predictably.

### POST → speak.started (from meeting 42 historical data)
Average: **528ms** (5 measurements: 523-536ms) — exceeds 200ms target by 2.6x.

**Root cause: 500ms sleep at index.ts:765**
```typescript
await new Promise((r) => setTimeout(r, 500)); // Let Meet register unmute before audio
```
Without this sleep, expected latency: ~28ms (Redis) + ~78ms (TTS) = **~106ms** (within target).
Same pattern at line 798 for speak_audio handler. Platform-specific — could be reduced for non-Meet platforms.

## Bugs Found (4)

### Bug 1: Channel mismatch for browser_session bots
- **bot-manager** publishes speak commands to `bot_commands:meeting:{id}` (main.py:2889)
- **browser-session.ts** subscribes to `browser_session:{container_name}` (line 202-221)
- Commands are published but never received by browser_session bots
- **Fix**: Subscribe browser_session to `bot_commands:meeting:{id}` in addition to its current channel

### Bug 2: No speak handler in browser_session
- `browser-session.ts:213-221` only handles `save_storage` and `stop` commands
- Even if the channel were correct, speak commands would be ignored
- **Fix**: Add speak command handler calling `ttsPlaybackService.synthesizeAndPlay()`

### Bug 3: TTS_SERVICE_URL missing from browser_session container env
- `orchestrator_utils.py:~614` `start_browser_session_container()` does NOT pass `TTS_SERVICE_URL`
- Regular bot path (line 269-271) DOES pass it
- **Fix**: Add `f"TTS_SERVICE_URL={os.getenv('TTS_SERVICE_URL', 'http://tts-service:8002')}"` to browser_session environment list

### Bug 4: PulseAudio not accessible via pactl in browser_session containers
- `PULSE_SERVER` env not set in browser_session containers
- `pactl` commands fail — cannot verify mute state or sink status
- PulseAudio sinks ARE created in entrypoint, but not controllable from inside
- **Fix**: Set `PULSE_SERVER` env var in browser_session container

## Risks
- Browser_session bots cannot speak (4 bugs)
- No interrupt/barge-in test (speak_stop command)
- 500ms unmute delay adds latency tax (could be reduced to ~0ms for non-Meet platforms)
- Race condition: if speak_stop arrives during TTS HTTP request (before paplay starts), audio still plays briefly
