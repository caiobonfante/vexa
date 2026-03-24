# Feature Log — Delivery

Append-only.

## Trajectory

| Date | Issue | Fix | Result |
|------|-------|-----|--------|
| 2026-03-21 | WS 0/43, REST 28/43 | Invalid platform_specific_id in test setup | 43/43 WS, 43/43 REST, 43/43 Postgres |
| 2026-03-22 | Two publishers (bot + collector) different formats → dashboard vanishing transcripts | Collector removed from WS publish, bot = single publisher, dashboard simplified to two-map model | All datasets pass |

## Dead Ends

[DEAD-END] **Two WS publishers (bot + collector)** — bot sent `transcript` bundles, collector sent `transcript.mutable` individual segments. Different formats to same channel. Dashboard had 5 dedup layers but keys didn't match. Fix: collector removed from WS entirely.

[DEAD-END] **Collector change detection + speaker mapping** — comparing existing vs new segments and running overlap analysis from speaker events. Unnecessary since bot segments are already producer-labeled. Removed — collector just HSETs.

[DEAD-END] **Invalid test meeting IDs** — meetings created with non-numeric `platform_specific_id` failed `Platform.construct_meeting_url()` validation. Fix: use valid 13-digit numeric Teams native IDs.

## Current Stage (2026-03-24)

Gate PASS at 80+. Dashboard rendering untested in live browser. Next: open dashboard during a live meeting to verify two-map model renders correctly.
