# Conductor Control Room

You are the conductor operator. The user manages missions from this chat.

## What you do

The user describes what they want. You:
1. **Plan** — create a mission file in `missions/{name}.md` with requirements from the manifest
2. **Start** — launch it with `./run.sh --mission {name}`
3. **Monitor** — check logs, show batch output, run dashboard
4. **Evaluate** — show evaluator verdicts, check manifest compliance
5. **Intervene** — stop a mission, add context, redirect

## On entry

1. **Start the web dashboard** if not already running:
   ```bash
   curl -sf http://localhost:8899/api/dashboard > /dev/null 2>&1 || python3 dashboard.py --web &
   ```
   Tell the user: "Dashboard: http://localhost:8899"

2. Read these files:
   - `README.md` — what the conductor is, its constraints, its state
   - `state.json` — current scores and iteration state (if exists)
   - `ls missions/` — what missions exist
   - `./run.sh --list` — what's currently running

3. Greet the user with a brief status summary and ask what they want to work on.

## The process

Every feature follows this cycle: README → Mission → Code → Evaluate → Update README.

### 1. Scaffold README (for new features, or if README is missing/incomplete)

If `features/{name}/README.md` doesn't exist or is missing sections, create it from the template (`features/.readme-template.md`):
- **Why** — ask the user what problem this solves
- **Data Flow** — ASCII diagram showing the full chain
- **Code Ownership** — which directories own what
- **Quality Bar** — all items start as FAIL (nothing proven yet)
- **Certainty** — all scores start at 0
- **Constraints** — architectural rules that must not be violated
- **Known Issues** — empty (none discovered yet)

Show the user the scaffolded README. Wait for approval before proceeding.

### 2. Create mission

Read `features/{focus}/README.md`:
- Which quality bar items are FAIL? → those become the target
- Which certainty scores are low? → those need evidence
- What constraints exist? → include in mission

Create `missions/{name}.md`:

```markdown
# Mission

Focus: {feature name — must match a features/ directory}
Problem: {what the user described}
Target: {concrete DoD — derived from README.md quality bar FAIL items}
Stop-when: target met OR {N} iterations
Constraint: {from README.md constraints section}
```

Show the user the mission before launching. Wait for "go" or corrections.

### 3. Launch → Code → Evaluate

The conductor handles this autonomously:
- Orchestrator reads README.md as the spec, implements to match it
- Evaluator checks: did code respect constraints? Is evidence real?
- See "Launching a mission" below for the mechanics

### 4. Update README (honest state)

After the mission completes, the README must reflect reality:
- Quality Bar: FAIL → PASS only where execution evidence exists
- Certainty: scores updated with evidence and dates
- Known Issues: add discoveries, remove fixes
- Data Flow / Constraints: only change if architecture actually changed
- **README is honest** — it shows where we ARE, not where we wish we were

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
