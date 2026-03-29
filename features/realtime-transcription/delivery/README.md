# Realtime Transcription — Delivery

Owns the right side of the pipeline: everything after core produces a segment update.

## Architecture

```
Bot produces segment update (segment_id, speaker, text, completed, absolute_start_time)
    |
    ├─ XADD transcription_segments {payload: JSON}    → collector persists
    └─ PUBLISH tc:meeting:{id}:mutable {JSON bundle}  → API gateway → WS → dashboard
    |
Collector (persistence only):
    XREADGROUP → HSET meeting:{id}:segments → background UPSERT Postgres
    |
REST: GET /transcripts/{platform}/{native_id}
    Postgres + Redis Hash → merge by segment_id → return all
    |
Dashboard: two-map model
    _confirmed (by segment_id, append-only) + _pendingBySpeaker (replaced per tick)
```

Bot is the single publisher for both live delivery (WS) and persistence (stream).
Collector is persistence-only — no WS publish, no mapping, no dedup.

## What "correct" means

Given N segment updates from the core pipeline:

1. **WS delivers all N** to any subscriber — no drops, no phantom segments
2. **REST returns latest state per segment_id** — no drops, no heuristic dedup
3. **Dashboard renders all unique segment_ids** — no disappearing on re-bootstrap
4. **Ordering** — segments sorted by absolute_start_time
5. **Latency** — WS within 1s of publish, REST within 30s+10s

## Delivery test

Single test: `replay-delivery-test.js`. Replays a raw dataset through the full pipeline
and validates at every WS tick that the rendered transcript state matches ground truth.

```bash
# Run with default dataset (teams-3sp-collection)
API_TOKEN=vxa_tx_... node replay-delivery-test.js

# Run with specific dataset
DATASET=teams-7sp-panel API_TOKEN=vxa_tx_... node replay-delivery-test.js
```

### What it validates

**At every WS tick:**
1. **Monotonic confirmed** — confirmed count never decreases (no vanishing segments)
2. **Speaker correctness** — each confirmed segment's speaker matches ground truth
3. **No phantoms** — every confirmed segment matches a GT utterance
4. **Progressive coverage** — GT coverage monotonically increases (no regressions)
5. **Pending sanity** — non-empty text, valid speaker

**After replay + immutability wait:**
6. **Full GT coverage** — every GT utterance covered by a confirmed segment
7. **REST match** — every WS confirmed segment appears in REST with same segment_id/speaker/text
8. **REST completeness** — REST has at least as many segments as WS confirmed

### How it works

1. Creates a meeting in Postgres (valid 13-digit numeric native ID)
2. Opens WS connection and subscribes **before** replay starts (no missed messages)
3. Spawns `production-replay` with `PUBLISH=true` and `MEETING_ID` pointing to pre-created meeting
4. On each WS `transcript` message: updates dashboard state model (exact replica of meetings-store.ts), runs validation checks
5. After replay exits: waits for immutability (45s), validates REST endpoint
6. Reports pass/fail with per-tick detail

### Output format

```
TICK   1 | 0C Alice:1P | covered: 0/12 | PASS
TICK   2 | 0C Alice:1P | covered: 0/12 | PASS
TICK   3 | 1C none     | covered: 1/12 | PASS
...
TICK  23 | 12C none    | covered: 12/12 | PASS

FINAL | REST: 12/12 | WS/REST match: 12/12 | PASS
DELIVERY: PASS (12/12 GT, 0 regressions, 0 phantoms, REST consistent)
```

## Development Notes

### Gate Criteria

| Check | Pass | Fail |
|-------|------|------|
| WS delivers all segments | N/N segments arrive via WS subscription | Any segment missing |
| REST returns latest state per segment_id | GET /transcripts matches WS | Missing or stale segments |
| Postgres persistence | Segments in DB after 30s immutability | Missing rows |
| Dashboard renders correctly | Two-map model: confirmed (by segment_id) + pending (by speaker) | Vanishing segments, duplicates |
| Ordering | Segments sorted by absolute_start_time | Out-of-order |
| Latency | WS within 1s of publish, REST within 30s+10s | Excessive delay |

### Edge Map

| Edge | From | To | Data format | Failure mode |
|------|------|----|-------------|--------------|
| Publish (stream) | SegmentPublisher | Redis XADD transcription_segments | JSON payload | Redis down -- segments lost |
| Publish (WS) | SegmentPublisher | Redis PUBLISH tc:meeting:{id}:mutable | JSON bundle | No subscribers -- silent drop |
| Consume | Redis stream | transcription-collector XREADGROUP | JSON | Consumer group lag |
| Persist | collector background task | Postgres UPSERT | SQL | DB down -- stuck in Redis |
| REST | api-gateway | Client | JSON merge Redis Hash + Postgres | Stale if background behind |
