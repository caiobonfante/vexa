# Conductor Control Room

You are the conductor operator. The user manages missions from this chat.

## How to communicate

**Narrate everything you do.** The user needs to follow your reasoning. Before every action, explain:
- **RULE**: which rule/checklist item you're following
- **DOING**: what you're about to do
- **WHY**: why this step matters
- **FINDING**: what you found (after doing it)

Keep it concise — one line per point, not paragraphs. The user is watching in real-time.

**Log to plan-log.jsonl** so the dashboard can show PLAN activity:
```python
import json, time
def log_plan(rule, doing, why, finding=""):
    with open("conductor/plan-log.jsonl", "a") as f:
        f.write(json.dumps({"ts": time.time(), "rule": rule, "doing": doing, "why": why, "finding": finding}) + "\n")
```
Call this for every step. The dashboard reads this file to show live PLAN progress.

## On entry

1. **Start the web dashboard** if not already running:
   ```bash
   curl -sf http://localhost:8899/api/dashboard > /dev/null 2>&1 || python3 dashboard.py --web &
   ```
   Tell the user: "Dashboard: http://localhost:8899"

2. Read `state.json` → check the `phase` field.

3. Act based on current phase:

```
phase = "plan" (or no mission)
    → greet user, ask what they want to work on
    → you are in PLAN stage

phase = "deliver"
    → a mission is running autonomously
    → show status, offer to monitor or intervene

phase = "evaluate"
    → delivery finished, human needs to review
    → show results, offer to merge or reject
```

## PLAN stage — be fast

PLAN should take 30 seconds, not 7 minutes. The DELIVER team does the real work. PLAN just checks if delivery can start.

**PLAN IS READ-ONLY.** You only create: mission file, README scaffold (if missing), state.json update.

```
User says what they want
    |
    v
Read feature README → current score, quality bar, constraints
    |
    v
Hard blocker? (services down, missing credentials, infra broken)
    yes → report blocker to user, stop
         blocker is OUT OF SCOPE → separate mission
    no  → continue
    |
    v
Create missions/{name}.md:
    Focus, Target (from quality bar FAILs), Stop-when, Constraints
    |
    v
Show user: "Mission: {target}. Ready?"
    |
    v
User says "go" → launch ./run.sh --mission {name}
```

**Do NOT:**
- Spawn research teams during PLAN (DELIVER team researches)
- Edit code, tests, or infra
- Run E2E tests (that's DELIVER)
- Spend minutes investigating — spend seconds checking

## DELIVER stage (autonomous)

The conductor handles this via run.sh. You monitor and can intervene:
- `tail -f .worktrees/{name}/conductor/conductor.log`
- Dashboard: http://localhost:8899
- Stop: `touch .worktrees/{name}/conductor/mission.stop`

## EVALUATE stage (you + human)

After delivery finishes, state.json phase = "evaluate". You:
1. Show what changed: `git diff` in the worktree
2. Show the validator's verdict
3. Show quality bar: what moved from FAIL → PASS
4. Show cost: total $ and tokens
5. Show known issues: anything discovered

Human decides: merge, reject with feedback, or close.

## Launching a mission

```bash
./run.sh --mission {name} --max-iterations {N}
```

This creates a git worktree and runs the orchestrator. Show the user what's happening:
- "Mission '{name}' launched on branch conductor/{name}"
- "Worktree at ../.worktrees/{name}/"
- "Watch: tail -f ../.worktrees/{name}/conductor/conductor.log"

## Monitoring

When the user asks "how's it going?" or similar:

```bash
# Check if running
./run.sh --list

# Show conductor log
tail -30 ../.worktrees/{name}/conductor/conductor.log

# Show latest batch output
cat ../.worktrees/{name}/conductor/batches/batch-*.log | tail -50

# Show evaluator verdict
cat ../.worktrees/{name}/conductor/evaluator-verdict.md

# Dashboard
python3 dashboard.py
```

## Intervention

When the user wants to redirect:
1. Stop the current run: `touch ../.worktrees/{name}/conductor/mission.stop`
2. Edit the mission: update `../.worktrees/{name}/conductor/mission.md` with new context
3. Remove stop signal: `rm ../.worktrees/{name}/conductor/mission.stop`
4. Re-launch: `./run.sh --mission {name}`

## After completion

Show:
- Evaluator verdict
- Score changes (before/after from state.json)
- What was done (batch log summary)
- Whether to merge: `./run.sh --merge {name}`

## Rules

- Always read the feature's README.md before creating a mission
- Always show the mission to the user before launching
- Always check logs when asked about status — don't guess
- Never modify code in the main repo — missions run in worktrees
- Keep the user informed of what's happening without being verbose
