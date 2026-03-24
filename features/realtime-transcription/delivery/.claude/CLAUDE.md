# Delivery Sub-Agent

> Parent: [realtime-transcription](../../.claude/CLAUDE.md)

## Mission

Own the right side of the pipeline: everything after core produces a segment update. Ensure WS delivers all segments live, REST returns correct state, collector persists correctly, dashboard renders without artifacts.

## Scope

You own: segment publishing (bot → Redis), collector persistence (Redis → Postgres), REST delivery (merge Redis Hash + Postgres), WS delivery (bot → api-gateway → dashboard), dashboard rendering model.

You don't own: audio capture, transcription, speaker identity, confirmation logic (those are core/platform concerns).

## Development cycle

Spec cycle: RESEARCH → SPEC → BUILD & TEST.

## Stage determination

1. Can you run the delivery replay test? (`node replay-delivery-test.js`)  NO → ENV SETUP
2. Does the replay test pass for all datasets?                             NO → BUILD & TEST
3. All datasets pass, WS + REST + Postgres consistent?                    YES → test with live meeting

## Gate

| Check | Pass | Fail |
|-------|------|------|
| WS delivers all segments | N/N segments arrive via WS subscription | Any segment missing |
| REST returns latest state per segment_id | GET /transcripts matches WS | Missing or stale segments |
| Postgres persistence | Segments in DB after 30s immutability | Missing rows |
| Dashboard renders correctly | Two-map model: confirmed (by segment_id) + pending (by speaker) | Vanishing segments, duplicates |
| Ordering | Segments sorted by absolute_start_time | Out-of-order |
| Latency | WS within 1s of publish, REST within 30s+10s | Excessive delay |

## Edges

| Edge | From | To | Data format | Failure mode |
|------|------|----|-------------|--------------|
| Publish (stream) | SegmentPublisher | Redis XADD transcription_segments | JSON payload | Redis down → segments lost |
| Publish (WS) | SegmentPublisher | Redis PUBLISH tc:meeting:{id}:mutable | JSON bundle | No subscribers → silent drop |
| Consume | Redis stream | transcription-collector XREADGROUP | JSON | Consumer group lag |
| Persist | collector background task | Postgres UPSERT | SQL | DB down → stuck in Redis |
| REST | api-gateway | Client | JSON merge Redis Hash + Postgres | Stale if background behind |

## Key architecture

Bot is single publisher for both WS (PUBLISH) and persistence (XADD). Collector is persistence-only — no WS publish, no speaker mapping, no dedup. Dashboard uses two-map model: `_confirmed` (by segment_id, append-only) + `_pendingBySpeaker` (replaced per tick).

## How to test

```bash
# Replay with default dataset
API_TOKEN=vxa_user_... node replay-delivery-test.js

# Replay with specific dataset
DATASET=teams-7sp-panel API_TOKEN=vxa_user_... node replay-delivery-test.js
```

## Critical findings
Save to `tests/findings.md`.
