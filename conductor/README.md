# Conductor

<!-- DESIGN -->

## Why

Software systems grow beyond what one person can hold in their head. AI agents can work on them, but unsupervised agents drift — they write code that works but violates the design, claim progress without evidence, ignore constraints, and celebrate prematurely.

The conductor is a framework for autonomous software improvement that solves this through four principles:

**Constraint-aware.** Every feature and service has a README that declares its design (data flow, ownership, constraints). The agent reads these before touching code. It knows what it's allowed to change and what it must preserve.

**Autonomous with boundaries.** The agent runs until it reaches the goal or hits a real blocker. It doesn't stop for convenience or declare partial success. It diagnoses, fixes, deploys, verifies — the full cycle in every iteration. When blocked by infrastructure it can't fix, it documents the blocker and stops honestly.

**Adversarial.** Generation and validation are separate roles with opposing incentives. The dev agent implements. The validator agent tries to disprove the claims. They work as a team — the validator catches issues during implementation, not after. Neither can override the other. Progress requires both to agree.

**Human interface.** The user manages everything from chat. Describe a mission → the framework runs it. Check progress → the dashboard shows live activity, costs, scores. Intervene → redirect the team mid-work. The user never edits config files, runs scripts manually, or reads raw logs.

## How It Works

Two layers: a dumb outer loop and a smart inner team.

```
OUTER LOOP (run.sh — bash, dumb, never makes decisions)
    |
    v
create worktree for mission (isolated git branch)
    |
    v
┌─────────────────────────────────────────────────────────┐
│ ITERATION (repeats until goal met, plateau, or limit)   │
│                                                         │
│   read mission.md → what's the target?                  │
│   read state.json → where are we?                       │
│   plateau? → inject alert                               │
│   last iteration rejected? → inject rejection context   │
│                                                         │
│   spawn claude session that creates:                    │
│   ┌───────────────────────────────────────────────────┐ │
│   │ INNER TEAM (TeamCreate — smart, collaborative)    │ │
│   │                                                   │ │
│   │  Dev agent                                        │ │
│   │    reads feature README (design) + service READMEs│ │
│   │    diagnoses → fixes → deploys → verifies         │ │
│   │    sends progress to validator as it works         │ │
│   │                                                   │ │
│   │  Validator agent                                  │ │
│   │    reviews dev's work in real-time                │ │
│   │    checks constraints, evidence, regressions      │ │
│   │    sends issues back DURING implementation        │ │
│   │    writes verdict: ACCEPT or REJECT               │ │
│   │                                                   │ │
│   │  Coordinator (chat session)                       │ │
│   │    monitors, relays to user                       │ │
│   │    user intervenes: "focus on X", "stop"          │ │
│   └───────────────────────────────────────────────────┘ │
│                                                         │
│   team finishes → update state files                    │
│   check-completion.py: target met?                      │
│       yes → STOP                                        │
│       no  → LOOP                                        │
│                                                         │
│   stop signal? (mission.stop file) → STOP               │
│   iteration limit? → STOP                               │
│   plateau? (same scores 3x) → STOP with diagnosis       │
│                                                         │
└─────────────────────────────────────────────────────────┘
    |
    v
MERGE (when ready)
    pre-merge gate:
        evaluator accepted?
        constraints not violated?
        no regressions?
        tests pass?
    all pass → merge worktree branch into main
    any fail → BLOCKED, show what failed
```

**The outer loop is deliberately dumb.** It doesn't understand the codebase, doesn't make decisions about what to fix, doesn't evaluate quality. It only asks: "are we done?" If not, it spawns the team again with context about what went wrong last time.

**The inner team is deliberately smart.** Dev and validator collaborate in real-time. The validator catches issues during implementation — not hours later in a separate review. The user can intervene through the coordinator at any point.

**The separation matters.** The dumb loop can't be talked out of continuing. The smart team can't avoid scrutiny. The human can steer without micromanaging.

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
