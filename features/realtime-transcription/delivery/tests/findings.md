# Delivery Findings

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| WS delivery | 90 | 43/43 segments via WS (meeting 470), 3/3 via WS (meeting 377, within 0.1s) | 2026-03-22 | Test with live meeting + dashboard |
| REST completeness | 90 | 43/43 via REST (meeting 470), 15/15 with segment_id (3sp), 31/31 (7sp) | 2026-03-22 | — |
| Postgres persistence | 90 | 43/43 in Postgres (meeting 470) | 2026-03-22 | — |
| Dashboard rendering | 80 | Two-map model deployed, legacy handler removed. Not tested with live meeting in browser. | 2026-03-22 | Open dashboard during live meeting, verify no vanishing/duplicates |
| Ordering | 80 | Normal segments ordered correctly. Giant segments (confirmation failure) interleave — but that's a core issue, not delivery. | 2026-03-23 | — |
| Single-publisher architecture | 90 | Collector WS publish removed. Bot is sole publisher. Dashboard only processes `transcript` bundles. | 2026-03-22 | — |

**Gate verdict: PASS** — all checks ≥ 80. Dashboard rendering at 80 (not live-tested in browser).

## Rollup

These scores feed into the parent feature's "Live segments via WebSocket", "REST /transcripts delivery", "WS and REST consistency", and "Dashboard rendering" checks.
