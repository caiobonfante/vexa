# Self-Improvement System — Feature Log

Append-only. Tracks what we tried to make the loop work.

## Trajectory

| Date | MVP | What happened | Result |
|------|-----|--------------|--------|
| 2026-03-24 | MVP0 attempt | Researcher agent read manifests, web-searched, found root causes for 3 GMeet blockers | PARTIAL — research works, no execution |
| 2026-03-24 | MVP1 attempt | 3-agent team (challenger + implementer + tester). Challenger refined hypothesis. Implementer coded fix. Tester claimed 9/9 pass without running tests. | FAIL — no execution evidence |
| 2026-03-24 | MVP1 retry | Lead manually ran `npx ts-node speaker-streams.test.ts` → 9/9 pass | PARTIAL — execution was manual, not agent-driven |
| 2026-03-24 | MVP1 retry 2 | Spawned executor agent to run tests. Executor couldn't find test data, got stuck on infrastructure discovery. | FAIL — manifests don't describe resources |

## Dead Ends

[DEAD-END] **Agent claims scores based on code review.** MVP1 tester said "9/9 pass" by reading code, not running tests. Score inflated from 40 to 60 without execution. Fix: Cost Ladder mandates execution evidence with command + stdout.

[DEAD-END] **Spawning agents without resource manifests.** Executor agent couldn't find test data, didn't know TTS port, had to discover infrastructure. Fix: resources table in CLAUDE.md + tools/ with confidence scores.

[DEAD-END] **Manual execution by lead.** Lead ran `npx ts-node` and logged it as system evidence. This proves the test works but not that agents can run it. The loop must be agent-driven.

[DEAD-END] **Skipping levels.** Attempted to jump from Level 1 to Level 5 (live meeting) because Level 2-3 data was missing. Cost Ladder says no skipping. Fix: agent must detect blocked levels, improve blocking tools, then retry.

## Current Stage

Building manifests. Tools not yet manifested. Resources tables not yet in product feature CLAUDE.md files. Must complete manifests before MVP0 can run.
