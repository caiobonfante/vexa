# Self-Improvement System — Findings

## Certainty Table


| Check                                          | Score | Evidence                                                                                             | Last checked |
| ---------------------------------------------- | ----- | ---------------------------------------------------------------------------------------------------- | ------------ |
| Agent reads manifests and produces findings    | 80    | MVP0: researcher read findings.md + feature-log.md, found root causes, wrote [EXTERNAL] entries      | 2026-03-24   |
| Team coordinates (research → implement → test) | 60    | MVP1: 3-agent team coordinated via tasks, challenger refined hypothesis, implementer coded fix       | 2026-03-24   |
| Agent executes tests (not just reads code)     | 50    | MVP1-retry: `npx ts-node speaker-streams.test.ts` → 9/9 pass. But run manually by lead, not by agent | 2026-03-24   |
| Score moves with execution evidence            | 30    | Score went 40→50 but based on manual execution, not agent-driven                                     | 2026-03-24   |
| Tool dependency chain resolves                 | 0     | Not tested — no agent has detected a blocked level and improved a tool                               | —            |
| Recursive tool improvement                     | 0     | Not tested                                                                                           | —            |
| Full loop (Level 1→5 autonomously)             | 0     | Not tested                                                                                           | —            |
| No human in loop (Levels 0-5)                  | 0     | Every MVP required human intervention                                                                | —            |


**Gate verdict: FAIL** — 4/8 checks at 0. The system can research and coordinate but cannot execute autonomously.

## Blocker

The loop doesn't close because:

1. Tools are not manifested — agent doesn't know what's available at what confidence
2. Resources table doesn't exist in product feature CLAUDE.md files yet
3. No agent has actually run `make unit` or `make play-`* — all execution was manual

## MVPs


| MVP  | What it proves                                        | Status   |
| ---- | ----------------------------------------------------- | -------- |
| MVP0 | Loop climbs cost ladder autonomously in one session   | NOT DONE |
| MVP1 | Loop fixes code AND validates with execution          | NOT DONE |
| MVP2 | Loop generates missing data using tools               | NOT DONE |
| MVP3 | Loop hosts live meeting for Level 5 validation        | NOT DONE |
| MVP4 | Orchestrator picks work across features, spawns teams | NOT DONE |
| MVP5 | Scheduled, continuous, no human trigger               | NOT DONE |


