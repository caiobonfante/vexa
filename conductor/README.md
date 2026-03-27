# Conductor — Self-Improvement Loop

## Why

The vexa codebase has 15 features, 12 services, and 42 agent configs. Improving any feature requires: reading the right docs, understanding the architecture, writing code that follows constraints, verifying with evidence, and updating docs. A human can't hold all of this in their head. An unsupervised agent drifts — writes code that works but violates the design, inflates scores, ignores constraints.

The conductor keeps agents running, focused, and honest. It reads the manifest (design intent), spawns agents that follow it, verifies their claims with a skeptical evaluator, and tracks progress across sessions. The human steers from chat — describes missions, monitors output, intervenes when needed.

## Data Flow

```
User describes mission in chat (or writes conductor/missions/{name}.md)
    |
    v
run.sh --mission {name}
    |
    v
worktree exists for this mission?
    no  → git worktree add .worktrees/{name}/ (isolated branch)
          copy conductor scripts + mission file into worktree
    yes → reuse existing
    |
    v
read mission.md → extract focus, target, stop-when
    |
    v
ITERATION LOOP (repeats until done, plateau, or limit):
    |
    v
    read state.json → current iteration, scores, last evaluation
    |
    v
    plateau detected? (same scores for 3+ iterations)
        yes → inject PLATEAU ALERT into orchestrator prompt
        no  → continue
    |
    v
    last evaluation was REJECTED?
        yes → inject rejection context into prompt
        no  → continue
    |
    v
    spawn orchestrator: claude -p --append-system-prompt-file (feature README.md)
        |
        v
    orchestrator reads README.md (system design), mission.md (objective)
        |
        v
    diagnose → fix → verify (autonomous, no human)
        |
        v
    stream-json events → batches/stream-N.jsonl (live, every tool call)
        |
        v
    parse-stream.py extracts:
        batches/batch-N.log   ← activity log (▶ BASH, ◀ READ, ✎ EDIT)
        batches/meta-N.json   ← cost, tokens, turns, files changed
    |
    v
    snapshot scores: check-completion.py reads all findings.md
        → update state.json with current scores
    |
    v
    spawn evaluator: claude -p --agent evaluator
        |
        v
    evaluator checks:
        did scores actually move? (git diff findings.md)
        is there execution evidence? (command + stdout, not prose)
        did anything regress? (compare score snapshots)
        constraints violated? (cross-service imports, ownership)
        |
        v
    writes evaluator-verdict.md → ACCEPT or REJECT with evidence
    |
    v
    check completion:
        mission target met?     → STOP: mission accomplished
        iteration limit hit?    → STOP: limit reached
        stop signal file exists? → STOP: user halted
        none of the above?      → LOOP: next iteration

---

dashboard.py :8899 (runs in background, serves web UI):
    reads: state.json, meta-N.json, batch-N.log, conductor.log, verdict
    serves: /api/dashboard (JSON), /api/batch/{name}, /api/logs/{name}
    auto-refreshes every 5s
    click mission → see activity log + evaluator verdict + conductor log

---

MERGE (after mission complete):
    run.sh --merge {name}
        |
        v
    pre-merge gate:
        1. evaluator verdict = ACCEPTED?
        2. mission focus matches changed files?
        3. no cross-service import violations?
        4. tests pass?
        5. no score regressions?
        |
        all pass → merge branch into main, clean up worktree
        any fail → BLOCKED, show what failed
```

## Code Ownership

```
conductor/run.sh                    → outer loop, worktree mgmt, spawn orchestrator + evaluator
conductor/check-completion.py       → score parsing, completion check, plateau detection
conductor/parse-stream.py           → stream-json → activity log + metadata
conductor/dashboard.py              → web + terminal dashboard, JSON API
conductor/dashboard.html            → web UI, auto-refreshes every 5s
conductor/missions/                 → per-job mission files
conductor/Makefile                  → make targets
conductor/CLAUDE.md                 → control room instructions (for interactive sessions)
.claude/agents/evaluator.md         → skeptical evaluator agent
.claude/commands/conductor-entry.md → ritualized session entry
.claude/commands/evaluate.md        → manual evaluator trigger
```

## Quality Bar

```
Orchestrator produces output     >0 bytes        stream-json working          PASS
Scores parsed correctly          match findings   median + Overall: pattern    PASS
Completion check detects done    exit 0           score-based + descriptive    PASS
Evaluator catches false claims   rejects >= 1     caught 4 bugs first run     PASS
Plateau detection fires          3 unchanged      logic exists, untested       PARTIAL
Parallel missions (worktrees)    2+ simultaneous  both produced output         PASS
Live streaming output            see agent work   stream-json → parse-stream   PASS
Intervention (pause/resume)      inject context   not implemented              FAIL
Cost tracking                    $/tokens shown   --output-format stream-json  PARTIAL
Design enforcement               check manifest   manifests exist, not wired   FAIL
```

## Gate

**PASS**: Describe mission in chat → conductor creates worktree → orchestrator runs → stream output visible in dashboard → evaluator verifies → scores + cost shown → manifest constraints not violated.

**FAIL**: Empty output, wrong scores, evaluator misses violations, dashboard stale, or constraints violated without detection.

## Certainty

```
run.sh spawns orchestrator           90   3 successful runs                       2026-03-27
check-completion.py parses scores    80   median + Overall: pattern working       2026-03-27
Evaluator produces verdict           90   caught 4 real bugs first run            2026-03-27
Worktree parallel missions           70   both ran, one ignored mission focus     2026-03-27
Dashboard web UI serves              90   HTML + JSON API on port 8899            2026-03-27
Stream output parsed                 80   parse-stream.py produces activity log   2026-03-27
Cost/token tracking                  30   stream-json has data, not displayed yet 2026-03-27
Intervention (pause/resume)           0   not implemented                         —
Design enforcement via manifest       0   manifests exist, not wired to evaluator 2026-03-27
```

## Documentation Flow

```
Agent starts a mission
    |
    v
read feature README.md ← this is the design intent (what SHOULD be true)
    |
    v
diagnose what's broken (compare README claims vs actual code behavior)
    |
    v
fix code to match README's quality bar
    |
    v
run tests, capture evidence (command + stdout)
    |
    v
update findings.md with evidence and new scores
    |
    v
did the code change what the feature does?
    yes → update README.md:
            Why section   ← stays (design intent, rarely changes)
            Data Flow     ← update if architecture changed
            Quality Bar   ← update current values
            Certainty     ← update scores + evidence
            Known Issues  ← add/remove as discovered
    no  → README stays as-is
    |
    v
evaluator checks:
    did code respect README constraints?
    does README still match code?
    any drift? → flag it, next iteration fixes it
```

**Order of operations** — every mission follows this:

1. **README.md** is the design intent. Agent reads it before touching code.
2. **Code** is changed to match the manifest's quality bar and fix known issues.
3. **findings.md** is updated with execution evidence (command + stdout, not prose).
4. **README.md** is updated from manifest + code:
   - **Why** — from manifest (problem, constraints, design decisions)
   - **What** — from code (what it does, architecture, key behaviors)
   - **How** — from code (how to run, configure, develop)

**Single source of truth:**
- Why it exists, design intent → `README.md`
- Current state, implementation → code + `findings.md`
- User-facing docs → `README.md` (derived from manifest + code, never invented from scratch)

**Drift detection:** The evaluator checks after each batch:
- Did code changes respect manifest constraints?
- Does README still match code?
- Does manifest still match reality? (if not, update manifest — it's a living doc)

## Constraints

- Conductor is a bash outer loop — does NOT decide what to work on, only whether to keep going
- All intelligence is in `claude -p` invocations — conductor is dumb orchestration
- State persists in files (state.json, conductor.log, batches/) — never in memory or context windows
- Each mission runs in its own git worktree — no shared mutable state between parallel missions
- Conductor MUST pass the feature's README.md to the orchestrator via `--append-system-prompt-file`
- Evaluator MUST check manifest constraints, not just score claims
- Score parsing uses findings.md as source of truth — state.json can be overwritten by snapshots
- Batch-written scores preserved via `max(parsed, existing)` in snapshots
- No hardcoded ports, budgets, or model names — all configurable via flags
- Dashboard reads from files only — no direct communication with running claude processes
- README.md MUST be updated when behavior changes and match this manifest

## Known Issues

- Orchestrator sometimes ignores mission focus and works on a different feature
- `check-completion.py` "Met: YES" too permissive for descriptive targets
- Evaluator verdict file path inconsistent between main conductor/ and worktrees
- No session persistence yet (`--resume` not wired)
- Stale files from earlier runs can confuse dashboard
