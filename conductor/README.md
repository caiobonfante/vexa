# Conductor

<!-- DESIGN -->

## Why

Software systems grow beyond what one person can hold in their head. AI agents can work on them, but unsupervised agents drift — they write code that works but violates the design, claim progress without evidence, ignore constraints, and stop before the job is done.

The conductor solves this with:

**Constraint-aware.** Feature and service READMEs declare design, constraints, and quality bar. These are injected into the agent's system prompt — the agent can't claim ignorance.

**Won't stop until done.** A Stop hook checks completion after every agent turn. If the mission target isn't met, it forces the agent to continue with specific feedback about what's missing. The agent can't declare victory early.

**Adversarial.** Dev and evaluator are separate sessions. Dev does the work. Evaluator reviews independently. Neither can override the other.

**Human-managed from chat.** User runs `cd conductor && claude`. Describes mission. Conductor launches it. Status line on every message.

## How It Works

```
User: "deliver ms-teams-revalidation"
    |
    v
Conductor creates mission file + builds prompt
    (feature README + service READMEs + mission)
    |
    v
claude --worktree {name} -p "do the work"
    --append-system-prompt-file prompt.txt
    |
    v
Dev agent works naturally
    reads README, understands pipeline, diagnoses, fixes, deploys, tests
    no micro-managing rules — agent decides how to work
    |
    v
Agent tries to stop → Stop hook fires
    |
    v
check-completion.py:
    mission target met? → evidence in findings.md?
        |
        yes → allow stop → session ends
        no  → block: "Still missing: {specific gaps}"
              → agent continues with this feedback
              → tries to stop again → hook fires again → loop
    |
    v
Dev session ends (target met or max turns)
    |
    v
claude --worktree {name} -p "evaluate what dev did"
    --agent evaluator
    --append-system-prompt-file same-prompt.txt
    |
    v
Evaluator reviews independently
    checks evidence, constraints, regressions
    writes verdict: ACCEPT {score} or REJECT
    |
    v
Conductor reports results to user
    user decides: merge or reject
```

## Three Stages

### PLAN (30 seconds, human-driven)

```
User says what they want
    → conductor reads feature README (score, quality bar)
    → hard blocker? → report, stop
    → create missions/{name}.md
    → build prompt (feature README + service READMEs + mission)
    → launch
```

PLAN is read-only. No code edits, no tests, no research teams.

### DELIVER (autonomous, Stop hook keeps it going)

```
claude --worktree {name} → dev works → Stop hook checks → loop until done
claude --worktree {name} → evaluator reviews → writes verdict
```

The Stop hook is the dumb loop. It can't be talked out of continuing. The agent can't declare victory without evidence.

### EVALUATE (human-driven)

```
Conductor shows: what changed, verdict, score, cost
User: merge / reject / close
```

## Stop Hook

The core mechanism. Configured in `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "type": "command",
        "command": "conductor/hooks/mission-check.sh",
        "timeout": 60
      }
    ]
  }
}
```

The hook:
```
Agent tries to stop
    |
    v
mission-check.sh fires
    → reads mission target from conductor/missions/{name}.md
    → runs check-completion.py
    → checks findings.md for execution evidence
    |
    target met with evidence → exit 0 (allow stop)
    not met → return {"decision":"block","reason":"Still missing: X, Y, Z"}
    → agent gets: "You wanted to stop but: Still missing: X, Y, Z"
    → agent continues
```

The hook prevents:
- "I'm done" without evidence
- Stopping after diagnosis without fixing
- Stopping after fixing without verifying
- Declaring score without execution proof

## How Agents Get Context

```
Mission says: Focus = meeting-aware-agent
    |
    v
Conductor reads features/meeting-aware-agent/README.md
    → Code Ownership section lists:
        services/api-gateway
        packages/agent-api
    |
    v
Conductor reads each service README
    |
    v
Builds prompt.txt:
    1. Mission file (focus, target, constraints)
    2. Feature README (why, data flow, quality bar, constraints)
    3. Service READMEs (constraints, boundaries)
    |
    v
claude --worktree {name} --append-system-prompt-file prompt.txt
    → agent has FULL context before starting
```

## README as Source of Truth

Every feature/service README has:

```
<!-- DESIGN: what we want. Can be ahead of code. -->
Why, Data Flow, Code Ownership, Constraints, Gate

---

<!-- STATE: what we have. Only updated with evidence. -->
Quality Bar, Certainty, Known Issues
```

Design = spec (aspirational). State = proof (never optimistic).

Documentation flow:
```
Before: README Design section written (PLAN stage)
During: dev works to match Design, updates State with evidence
After:  evaluator checks State matches code, README honest
```

## Architecture

```
conductor/
    CLAUDE.md                  → control room (this is the conductor)
    README.md                  → system design (this file)
    missions/                  → per-job mission files
    check-completion.py        → completion checker (Stop hook calls this)
    hooks/mission-check.sh     → Stop hook script
    state.json                 → scores (seeded from findings)

.claude/
    agents/evaluator.md        → skeptical evaluator
    agents/researcher.md       → research agent
    settings.json              → Stop hook config

features/{name}/
    README.md                  → Design + State
    tests/findings.md          → execution evidence
```

No run.sh. No dashboard. No parse-stream.py. No worktree setup code.
Native `claude --worktree` for isolation. Stop hook for the loop.

## Constraints

- Stop hook is the ONLY loop mechanism — no bash loops
- Agent gets full README context via --append-system-prompt-file
- Dev and evaluator are separate sessions — dev can't self-validate
- Evaluator can reject but can't fix
- Human controls PLAN and EVALUATE — machine controls DELIVER
- README State section only updated with execution evidence
- Native --worktree for isolation — no custom worktree code

---

<!-- STATE -->

## Quality Bar

```
Stop hook forces continuation         native, no bash loop              NOT IMPLEMENTED
Native worktree isolation             claude --worktree                 NOT IMPLEMENTED
Context injection via prompt file     feature + service READMEs         PASS
Adversarial validation                separate evaluator session        PASS
Completion check                      check-completion.py               PASS (rewritten)
README as source of truth             Design/State split                PASS
Status line in chat                   PLAN/DELIVER/EVALUATE prefix      PASS
```

## Certainty

```
check-completion.py works              80   rewritten, tested             2026-03-28
Evaluator catches false claims         90   caught 4+ bugs                2026-03-28
README context auto-appended           80   code ownership chain works    2026-03-28
Stop hook mechanism                     0   not implemented               —
Native worktree                         0   not tested with conductor     —
```

## Known Issues

- Stop hook not implemented yet (this is the next step)
- Need to test claude --worktree with --append-system-prompt-file
- Team conversation in subagent .jsonl files — accessible but not wired into monitoring
- check-completion.py needs to work as a Stop hook (read mission from env/file, return JSON)
