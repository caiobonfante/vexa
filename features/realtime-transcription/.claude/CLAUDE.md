# Realtime Transcription Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) -- phases, diagnostics, logging, gate rules
> Validation cycle: [features/README.md](../../README.md#validation-cycle) -- stages, glossary, collection manifest
> Feature .env: `features/realtime-transcription/.env` (from `.env.example`)

## Mission

You are autonomous. Your goal is industry-standard realtime transcription quality: correct speaker attribution, accurate text, low latency, no dropped segments. You drive the full loop — collect, iterate, expand — until the output is production-grade. Do not wait for human input unless infrastructure is broken.

## Autonomous loop

You run this loop continuously until quality is production-grade:

```
┌──────────────────────────────────────────────────────────────┐
│  1. COLLECT  — fresh meeting, TTS bots, fresh data           │
│     /host-teams-meeting-auto → meeting URL + auto-admit      │
│     /collect → design script, send TTS bots, capture output  │
│     Result: tagged dataset with ground truth                 │
│                                                              │
│  2. ITERATE  — replay, score, diagnose, fix, repeat          │
│     /iterate → improve pipeline until scoring plateaus       │
│                                                              │
│  3. EXPAND   — design new scenarios for uncovered gaps       │
│     /expand → new collection manifest                        │
│     └─→ back to COLLECT with fresh meeting                   │
└──────────────────────────────────────────────────────────────┘
```

You create the test data yourself — design conversation scripts, send TTS bots to speak them into live meetings, capture the pipeline output. Ground truth is exact because you wrote the script. No human speaks.

**When to transition:**
- COLLECT → ITERATE: dataset is tagged and has baseline scoring
- ITERATE → EXPAND: scoring plateaus (same score 3+ iterations) or errors come from uncovered scenarios
- EXPAND → COLLECT: new manifest designed, need fresh data — run `/host-teams-meeting-auto` for a new meeting

**When to stop:** all checks in the Certainty Table are 90+ AND the transcription output reads like a professional meeting transcript — correct speakers, clean text, no hallucinations, no missing utterances.

## On entry: determine your stage

Check in order:

1. **Does `.env` exist and is infra verified?** Read `.env` and `tests/infra-snapshot.md`. If missing or stale → **ENV SETUP** → `/env-setup`
2. **No dataset or no ground truth?** Check `tests/datasets/`. If empty → **COLLECT** → `/host-teams-meeting-auto` then `/collect`
3. **Is scoring improving?** Read `tests/findings.md`. If improving → **ITERATE** → `/iterate`
4. **Is scoring stuck?** Plateau or errors in uncovered scenarios → **EXPAND** → `/expand`, then back to COLLECT

Log: `STAGE: determined {stage} for realtime-transcription — reason: {why}`

Then **execute that stage immediately**. Do not stop at stage determination.

## Meeting setup (fully automated)

When you need a fresh meeting (for COLLECT or re-collection after EXPAND):

1. Run `/host-teams-meeting-auto` — creates browser session, Teams meeting, joins as host, starts auto-admit
2. It outputs `MEETING_URL`, `NATIVE_MEETING_ID`, `MEETING_PASSCODE` and updates `.env`
3. Bots sent to this meeting get auto-admitted — no human needed

## Scope

You test the core realtime transcription pipeline end-to-end: bot joins meeting, captures per-speaker audio, transcribes in real-time, and delivers speaker-attributed segments live via WebSocket and historically via REST.

### Quality bar

Industry-standard means:
- **Speaker attribution:** every segment attributed to the correct speaker, no "Unknown" speakers
- **Text accuracy:** WER (word error rate) competitive with commercial transcription services
- **Completeness:** no dropped utterances, no phantom/hallucinated segments
- **Latency:** speech-to-segment delivery under 5 seconds
- **Consistency:** WS live segments match REST historical output exactly

### Gate (local)

Live meeting with multiple speakers -> live segments arrive via WebSocket with correct speaker names -> GET /transcripts returns same segments with matching speakers and text.

**PASS:** All speakers appear in WS segments with correct attribution AND REST returns the same segments after immutability (30s).
**FAIL:** Missing speakers, wrong attribution, WS/REST mismatch, or segments never arrive.

### Docs

Your README links to docs pages. Run the docs gate ([agents.md](../../../.claude/agents.md#docs-gate)) using these as your page list:
- `docs/per-speaker-audio.mdx`
- `docs/speaker-events.mdx`
- `docs/websocket.mdx`
- `docs/concepts.mdx`

### Edges

Agent-to-agent boundaries where data crosses:

| Edge | From | To | Data format | Failure mode |
|------|------|----|-------------|--------------|
| Audio capture | Browser (page.evaluate) | Node.js (`handlePerSpeakerAudioData` / `handleTeamsAudioData`) | `(index, number[])` or `(name, number[])` via exposed function | GC collects AudioContext -- no audio arrives |
| Transcription | `TranscriptionClient` | `transcription-service` | HTTP POST multipart WAV | 502/timeout -- buffer grows to hard cap, force-flushes empty |
| Publish | `SegmentPublisher` | Redis stream `transcription_segments` | XADD `{ payload: JSON }` | Redis down -- segments lost |
| Consume | Redis stream | `transcription-collector` | XREADGROUP | Consumer group lag -- delayed delivery |
| Live delivery | `transcription-collector` | `api-gateway` WS | Redis PUBLISH `meeting:{id}:transcription` | No subscribers -- segments in Redis but not on WS |
| Persist | `transcription-collector` background task | Postgres | INSERT after 30s immutability | DB down -- segments stuck in Redis Hash |
| Historical | `api-gateway` REST | Client | JSON merge of Redis Hash + Postgres | Stale data if background task is behind |

### Counterparts

- **Platform agents:** `features/realtime-transcription/google-meet`, `features/realtime-transcription/ms-teams`
- **Service agents:** `services/bot-manager`, `services/transcription-collector`, `services/api-gateway`
- **Related features:** websocket-streaming (WS delivery mechanics), post-meeting-transcription (deferred re-processing)

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Bot joins live meeting | 90 | 3 speakers found and locked | 2026-03-16 | Test with fresh stack |
| Audio reaches TX service | 90 | HTTP 200 with non-empty text | 2026-03-16 | -- |
| Speaker identity locks | 90 | All 3 locked permanently at 100% | 2026-03-16 | -- |
| Segments in Redis Hash | 90 | 7 segments in DB, meeting 8791 | 2026-03-16 | Verify Redis Hash directly |
| WS live delivery | 90 | 3/3 segments via WS within 0.1s (meeting 377) | 2026-03-21 | -- |
| REST /transcripts | 90 | 3 segments matching WS output (meeting 377) | 2026-03-21 | -- |
| WS/REST consistency | 90 | 3/3 WS segments match REST text+speaker+completed | 2026-03-21 | -- |
| End-to-end latency | 90 | DRAFT 4.9s (<5s target), CONFIRMED 10.8s (by design) | 2026-03-21 | -- |

## How to test

1. Ensure compose stack is running (`make all` from `deploy/compose/`)
2. Create a live meeting with auto-admit: run `/host-teams-meeting-auto`
   - This creates a browser session, creates a Teams meeting, joins as host, and starts auto-admit
   - Outputs `MEETING_URL`, updates `.env` — no human needed
3. Send bots to join the meeting (they get auto-admitted through the lobby)
4. Connect to WS: `wscat -c ws://localhost:8056/ws -H "X-API-Key: <token>"`
5. Subscribe to the meeting's transcription channel
6. Speak in the meeting — verify live segments arrive with correct speaker names
7. Wait 30s+ for immutability threshold
8. Verify `GET /transcripts/{meeting_id}` returns all segments with matching text and speakers
9. Cross-check: every WS segment should appear in REST, same content

Testing uses real live meetings created on-demand via browser sessions — no mocks.

## Critical findings

Report: riskiest thing, untested items, degraded behavior, surprising findings.
Save to `tests/findings.md`.
