# Bot Lifecycle — Test Findings

> Last updated: 2026-03-28
> Status: E2E tests running against live Google Meet

## Confidence Gate

| Check | Score | Evidence |
|-------|-------|----------|
| T1.1 Full lifecycle (waiting room) | 90 | PASSED: requested→joining→awaiting_admission→active→stopping→completed in 24s. 5 transitions with timestamps verified. meeting_id=262, meeting=xtf-dwpa-miw, 2026-03-28 |
| T1.2 Bot stop while active | 90 | PASSED: 30s soak, clean stop, completion_reason=stopped. 2026-03-28 |
| T2.1 Left alone | 0 | SKIPPED: requires host CDP control to simulate host leaving |
| T2.2 Admission timeout | 0 | NOT RUN YET: needs auto-admit stopped + real meeting |
| T3.1 Invalid meeting URL | 90 | PASSED: failed with failure_stage + error_details populated. 135.88s. 2026-03-28 |
| T4.1 Join speed baseline | 60 | Baseline: 16s to awaiting_admission, 22s to active. Target: <10s to awaiting_admission |
| Redis pub/sub verification | 30 | Redis collector captures 0 events — likely different Redis DB or async publish timing. Status transitions verified via API instead. |

Gate: **3/7 checks ≥ 80** — T1.1, T1.2, T3.1 pass. T2.2 not run, T2.1 skipped, T4.1 needs optimization, Redis needs investigation.

## Timing Baseline

| Segment | Duration | Target |
|---------|----------|--------|
| POST → requested | <1s | <1s |
| requested → joining | 6s | - |
| joining → awaiting_admission | 10s | - |
| **POST → awaiting_admission** | **16s** | **<10s** |
| awaiting_admission → active | 6s (auto-admit) | - |
| POST → active | 22s | - |
| stop → completed | 2s | - |

## Auto-admit Fix

Google Meet changed Admit buttons from `<button>` to `<span>`. Fixed in `auto-admit.js` — selectors now match both `button` and `span` elements, plus use `getByRole` for accessibility-based matching.

## Known Issues

1. **Redis pub/sub**: collector gets 0 events despite pattern subscribe before bot creation. Meeting-api likely publishes on a different Redis connection or DB. Verification relies on `status_transition` array from GET /bots instead.
2. **Join speed**: 16s to awaiting_admission, target is <10s. Container start is 6s, browser navigation is 10s.
