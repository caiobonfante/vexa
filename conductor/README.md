# Conductor

<!-- DESIGN -->

## Why

Software systems grow beyond what one person can hold in their head. AI agents can work on them, but unsupervised agents drift — they write code that works but violates the design, claim progress without evidence, ignore constraints, and celebrate prematurely.

The conductor is a framework for autonomous software improvement that solves this through four principles:

**Constraint-aware.** Every feature and service has a README that declares its design (data flow, ownership, constraints). The agent reads these before touching code. It knows what it's allowed to change and what it must preserve.

**Autonomous with boundaries.** The agent runs until it reaches the goal or hits a real blocker. It doesn't stop for convenience or declare partial success. It diagnoses, fixes, deploys, verifies — the full cycle in every iteration. When blocked by infrastructure it can't fix, it documents the blocker and stops honestly.

**Adversarial.** Generation and validation are separate roles with opposing incentives. The dev agent implements. The validator agent tries to disprove the claims. They work as a team — the validator catches issues during implementation, not after. Neither can override the other. Progress requires both to agree.

**Human interface.** The user manages everything from chat. Describe a mission → the framework runs it. Check progress → the dashboard shows live activity, costs, scores. Intervene → redirect the team mid-work. The user never edits config files, runs scripts manually, or reads raw logs.

## Three Stages

```
PLAN → DELIVER → EVALUATE
```

Each stage has different roles, different outputs, and different trust models.

### Stage 1: PLAN (human-driven)

```
Roles: human + conductor + researcher

Human describes what they want
    |
    v
Conductor reads existing READMEs
    → what's the current state?
    → what's already designed vs what's missing?
    |
    v
Researcher investigates (if needed)
    → read code to understand current behavior
    → check existing endpoints, services, infra
    → report findings
    |
    v
Human + conductor update READMEs
    → scaffold new feature README (Design section: why, data flow, constraints)
    → update service READMEs if new contracts needed
    → all quality bar items = FAIL, all certainty = 0
    |
    v
Create mission file
    → focus, target (from README quality bar FAILs), constraints, iteration limit
    → human approves before launch

Output:  updated READMEs (Design), mission file, worktree
Trust:   human is the authority
```

### Stage 2: DELIVER (autonomous, adversarial)

```
Roles: dev agent + validator agent, inside a dumb loop

DUMB LOOP (bash — keeps going, never makes decisions):
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   read mission + state → where are we?                  │
│   plateau? → inject alert                               │
│   last iteration rejected? → inject context             │
│                                                         │
│   SMART TEAM (TeamCreate — dev + validator):            │
│   ┌───────────────────────────────────────────────────┐ │
│   │                                                   │ │
│   │  Dev agent                                        │ │
│   │    reads feature + service READMEs                │ │
│   │    diagnoses → fixes → deploys → verifies         │ │
│   │    sends progress to validator as it works         │ │
│   │                                                   │ │
│   │  Validator agent                                  │ │
│   │    reviews in real-time (not after)               │ │
│   │    checks constraints, evidence, regressions      │ │
│   │    sends issues back DURING implementation        │ │
│   │    writes verdict: ACCEPT or REJECT               │ │
│   │                                                   │ │
│   └───────────────────────────────────────────────────┘ │
│                                                         │
│   team finishes → update README State section            │
│   check-completion.py: target met?                      │
│       yes → STOP                                        │
│       no  → LOOP (spawn team again with rejection context) │
│                                                         │
│   stop signals: mission.stop file, iteration limit,     │
│                 plateau (same scores 3x)                │
│                                                         │
└─────────────────────────────────────────────────────────┘

Output:  code changes, updated READMEs (State section), findings.md
Trust:   nobody — adversarial by design
```

The dumb loop can't be talked out of continuing. The smart team can't avoid scrutiny. Dev and validator have opposing incentives — progress requires both to agree.

### Stage 3: EVALUATE (human-driven)

```
Roles: human + conductor

Conductor reports:
    → what files changed (git diff)
    → what the dev claimed vs what the validator found
    → cost, tokens, iterations
    → quality bar: what moved from FAIL → PASS
    → what's still broken (known issues)
    |
    v
Human reviews
    → does this actually work? (manual testing in the wild)
    → do the README changes make sense?
    → are the constraints still right?
    |
    v
Decision:
    merge   → pre-merge gate (constraints, regressions, evidence)
              → merge worktree branch into main
    reject  → update mission with feedback, re-run DELIVER
    close   → not worth pursuing, clean up worktree

Output:  merged code or rejection with reasons
Trust:   human is the authority
```

### Why three stages

Plan and Evaluate are human-driven. Delivery is autonomous. The human bookends the work — sets direction, then judges the result. The machine runs in between.

The machine never decides WHAT to build (Plan) or WHETHER it's good enough (Evaluate). It only decides HOW to build it (Deliver) — and even then, it's adversarial.

## Principles

### README is the single source of truth

Every feature and service has a README with two sections:

```
<!-- DESIGN: what we want. Can be ahead of code. -->
Why, Data Flow, Code Ownership, Constraints, Gate

---

<!-- STATE: what we have. Only updated with evidence. -->
Quality Bar, Certainty, Known Issues
```

Design is the spec — it can be aspirational. State is the proof — it's never optimistic. They converge when the feature is done. The evaluator checks State against code, not Design against code.

### Evidence-based progress

Scores only move with execution evidence:

```
VALID evidence:    command + stdout ("curl returned 200, body contains 6 segments")
INVALID evidence:  prose ("the code looks correct", "should work based on review")
```

Quality bar items stay FAIL until proven. Certainty scores require specific evidence with dates. The evaluator rejects claims without proof.

### Adversarial validation

Dev and validator have opposing incentives:

```
Dev's goal:        make progress, advance scores, ship features
Validator's goal:  find what's wrong, reject inflated claims, catch drift

Neither can override the other:
    dev says PASS + validator says PASS → accepted
    dev says PASS + validator says FAIL → rejected (validator explains why)
    dev can't skip validation
    validator can't make changes
```

### Constraint enforcement

The conductor passes feature README + all owned service READMEs to the agent. Constraints are in the system prompt — the agent can't claim it didn't know.

```
Feature README says: "all API calls go through gateway"
Service README says: "agent-api accepts calls from gateway only"
    → agent imports agent-api directly → constraint violation
    → evaluator catches it → rejected
    → pre-merge gate blocks it
```

### Documentation flow

```
Before implementation:
    1. Scaffold feature README (Design section: why, data flow, constraints)
    2. Scaffold service READMEs if needed (new contracts)
    3. All quality bar items = FAIL, all certainty = 0

During implementation:
    4. Dev agent reads READMEs → implements to match Design
    5. Validator reviews against README constraints in real-time

After implementation:
    6. Update README State section (quality bar, certainty, known issues)
    7. Only FAIL → PASS where execution evidence exists
    8. Known issues: add discoveries, remove fixes
    9. Design section: only change if architecture actually changed
```

## Components

```
conductor/CLAUDE.md          → control room (interactive sessions, team management)
conductor/run.sh             → worktree setup, state management, iteration loop
conductor/check-completion.py → score parsing, plateau detection, completion check
conductor/parse-stream.py    → stream-json → activity log
conductor/dashboard.py       → web dashboard :8899 (JSON API + HTML)
conductor/dashboard.html     → web UI (auto-refresh, live activity log)
conductor/missions/          → per-job mission files
.claude/agents/evaluator.md  → skeptical evaluator agent definition
```

## Observability

```
Web dashboard (http://localhost:8899):
    → mission cards: status, cost, duration, tokens
    → batch output: live activity log (▶ BASH, ◀ READ, ✎ EDIT)
    → evaluator verdict: ACCEPT/REJECT with evidence
    → conductor log: iteration decisions, plateau detection
    → feature scores: bar chart of all features

Chat interface:
    → "how's it going?" → show progress summary
    → "stop" → halt the team
    → "focus on X instead" → redirect
    → "merge" → run pre-merge gate
```

---

<!-- STATE -->

## Quality Bar

```
Team-based execution (TeamCreate)     dev + validator collaborate     FAIL (sequential today)
Constraint enforcement                README constraints in prompt    PASS (auto-appended)
Adversarial validation                evaluator catches real bugs     PASS (caught 4+ bugs)
Live activity streaming               see tool calls as they happen  PASS (parse-stream.py)
Cost tracking                         $/tokens per iteration         PASS ($4.59 captured)
Plateau detection                     3 unchanged → alert            PARTIAL (logic exists)
Human intervention                    redirect mid-run from chat     FAIL (stop file only)
Pre-merge gate                        blocks on violations           PASS (5 checks)
Completion check accuracy             no false positives             FAIL (too permissive)
README auto-append to prompt          feature + service READMEs      PASS (code ownership chain)
```

## Certainty

```
Orchestrator runs autonomously        90   multiple missions completed              2026-03-28
Evaluator catches false claims        90   rejected inflated scores, auth bugs      2026-03-28
Score parsing from findings           80   median + Overall: pattern                2026-03-27
Worktree isolation                    70   works but cwd bug caused main repo edits 2026-03-28
Dashboard serves live data            90   HTML + JSON API on :8899                 2026-03-27
Stream output parsed                  80   activity log with tool calls             2026-03-28
Cost tracking                         80   $4.59 + $0.83 captured from stream-json  2026-03-28
Pre-merge gate                        70   5 checks, stale verdict bug found        2026-03-28
Team-based execution                   0   not implemented (sequential today)       —
Human intervention via chat            0   stop file only, no mid-run redirect      —
Completion check accuracy             30   descriptive targets too permissive       2026-03-28
```

## Known Issues

- Completion check too permissive — "pass" anywhere in findings triggers "met"
- Evaluator reads stale verdicts from previous missions
- Worktree cwd bug: orchestrator sometimes writes to main repo instead of worktree
- Sequential dev → evaluator means issues caught late, not during implementation
- `run.sh` is both worktree manager and execution engine — should be separated
- No `--resume` session persistence across iterations
- Dashboard doesn't render Mermaid or markdown in batch output
