# Post-Meeting Transcription Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
You test post-meeting transcription: after a meeting ends, the system re-transcribes the full recording with better quality and improved speaker mapping. You dispatch service agents — you don't write code.

### Gate (local)
Meeting ends → deferred transcription produces improved transcript → speaker mapping >=70% correct vs source. PASS: improved transcript generated with better speaker accuracy. FAIL: deferred transcription not triggered or speaker mapping below threshold.

### Docs
Your README links to your docs pages. Run the docs gate ([agents.md](../../../.claude/agents.md#docs-gate)) using those links as your page list.

### Edges
**Crosses:**
- transcription-collector (triggers deferred processing)
- transcription-service (re-transcribes full recording)
- bot-services (provides recording)
- Postgres (stores improved transcript)

**Data flow:**
recording file → transcription-service → transcription-collector (SPLM) → Postgres update → api-gateway serves improved version

### Counterparts
- Service agents: `services/transcription-collector`, `services/api-gateway`
- Related features: realtime-transcription (live version that gets improved), audio-recording (recording source)

## How to test
1. Dispatch service agents for transcription-collector, api-gateway
2. Complete a meeting with known speakers
3. Verify deferred transcription is triggered after meeting ends
4. Compare improved transcript speaker mapping to source (>=70% threshold)
5. Verify GET /transcripts serves the improved version

## Critical findings
Report: riskiest thing, untested items, degraded behavior, surprising findings.
Save to `tests/findings.md`.
