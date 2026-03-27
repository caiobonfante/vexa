# Conductor — Recursive Self-Improvement Loop

The conductor is the outer loop that keeps the self-improvement system running. You write a mission, run one command, and walk away. The system autonomously diagnoses, fixes, verifies, and iterates until the mission is accomplished or it gets stuck.

## How it works

```
You write mission.md          The conductor reads it
        │                              │
        ▼                              ▼
┌─────────────┐    spawn    ┌──────────────────┐
│  conductor  │ ─────────►  │  orchestrator    │
│  (bash loop)│             │  (claude -p)     │
│             │  ◄────────  │  diagnose → fix  │
│  check done │   output    │  → verify        │
│  snapshot   │             └──────────────────┘
│  evaluate   │    spawn    ┌──────────────────┐
│             │ ─────────►  │  evaluator       │
│             │             │  (skeptical)     │
│  loop?      │  ◄────────  │  accept/reject   │
└─────────────┘   verdict   └──────────────────┘
```

Each iteration:
1. **Orchestrator** reads mission + state files, diagnoses the problem, fixes it, verifies
2. **Score snapshot** taken from findings files
3. **Evaluator** reviews claims — rejects inflated scores, confirms real progress
4. **Completion check** — mission met? plateau? iteration limit?
5. If not done → loop with fresh context (rejection/plateau fed into next iteration)

## Quick start

```bash
# 1. Edit the mission
vim conductor/mission.md

# 2. Run
make conductor              # one iteration
make conductor-loop N=5     # up to 5 iterations

# 3. Watch
make conductor-log          # conductor decisions
make conductor-batch        # full agent output from latest iteration
make conductor-status       # scores + mission progress
```

## Files

| File | Purpose |
|------|---------|
| `mission.md` | **Your steering wheel.** What to work on, definition of done, constraints. |
| `state.json` | Machine-readable state. Scores, iteration count, evaluation results. Seeded from findings. |
| `conductor.log` | Timeline of conductor decisions. One line per event. |
| `batches/batch-N.log` | Full claude output for iteration N. |
| `batches/eval-N.log` | Full evaluator output for iteration N. |
| `batches/prompt-N.txt` | The prompt sent to claude for iteration N (debugging). |
| `evaluator-verdict.md` | Latest evaluator verdict (ACCEPT/REJECT with evidence). |
| `run.sh` | The conductor script (bash). |
| `check-completion.py` | Score parsing, completion check, plateau detection. |
| `Makefile` | All make targets. |

## Mission file format

```markdown
# Mission

Focus: dashboard bot lifecycle
Problem: can't create and stop a meeting transcription bot from the dashboard
Target: bot create + stop works end-to-end from dashboard, verified in browser
Stop-when: target met OR 5 iterations
Constraint: don't rebuild vexa-bot image
```

| Field | Required | Description |
|-------|----------|-------------|
| Focus | yes | Short name for the area of work |
| Problem | yes | What's broken or missing |
| Target | yes | Definition of done. Can be descriptive or score-based (`score >= 80`) |
| Stop-when | yes | When the conductor should stop (`target met OR N iterations`) |
| Constraint | no | What NOT to touch |

Edit `mission.md` while the conductor is running — it re-reads it between iterations.

## Make targets

From repo root (`make conductor-*`) or from `conductor/` directly (`make -C conductor *`):

| Target | Description |
|--------|-------------|
| `make conductor` | Run one iteration |
| `make conductor-loop N=5` | Loop up to N iterations (default: 10) |
| `make conductor-status` | Show mission, scores, plateau status |
| `make conductor-dry` | Seed state + show status, don't run |
| `make conductor-seed` | Reseed state.json from current findings |
| `make conductor-stop` | Create stop signal — halts after current iteration |
| `make conductor-resume` | Clear stop signal |
| `make conductor-log` | Tail conductor log (last 50 lines) |
| `make conductor-batch` | Show full output of latest iteration |
| `make conductor-evaluate` | Manually run the evaluator |
| `make conductor-verdict` | Show latest evaluator verdict |
| `make mission` | Open mission.md in your editor |

## How to steer

**Before running:** Edit `mission.md` with your objective.

**During a run:** Edit `mission.md` — the conductor re-reads it between iterations.

**Emergency stop:** `make conductor-stop` (or `touch conductor/mission.stop`). Conductor halts after the current iteration finishes.

**Check progress:** `make conductor-status` shows scores and whether the mission is met.

**See what happened:** `make conductor-batch` shows full agent output. `make conductor-log` shows conductor-level decisions.

## Plateau detection

If scores don't change for 3 consecutive iterations (configurable via `P=N`), the conductor:
1. Logs `PLATEAU DETECTED`
2. Injects a "PLATEAU ALERT" into the next orchestrator prompt
3. Forces the orchestrator to reassess its approach

This prevents the system from doing the same thing repeatedly and expecting different results.

## Evaluator

After each iteration, a separate skeptical evaluator agent reviews all claims:
- Did scores actually change? (git diff on findings.md)
- Is there execution evidence? (command + stdout, not just "code looks right")
- Did anything regress?
- Is the team celebrating prematurely? (mock vs real, curl vs browser)

If the evaluator **rejects**, the rejection context is injected into the next iteration's prompt. The orchestrator must address the rejection before claiming progress.

Evaluator config: `.claude/agents/evaluator.md`

## Architecture

The conductor is intentionally dumb — a bash loop that spawns smart agents. This follows the [Anthropic harness design pattern](https://www.anthropic.com/engineering/harness-design-long-running-apps):

- **Generator-Evaluator split**: Orchestrator generates, Evaluator reviews. Separate agents because self-evaluation produces overconfident results.
- **Initializer-Executor pattern**: Every session starts by reading state files. No reliance on context window memory.
- **JSON state**: `state.json` is machine-readable. The conductor parses it programmatically. Agents can't accidentally rewrite the spec.
- **File-based handoffs**: All state persists in files. Context windows die; files don't.

## CLI reference

```bash
./conductor/run.sh [OPTIONS]

Options:
  --max-iterations N      Max iterations (default: 10)
  --plateau-threshold N   Unchanged iterations before plateau (default: 3)
  --budget USD            Max spend per iteration (default: unlimited)
  --dry-run               Seed state + show status, don't run
  --status                Show current status
  -h, --help              Show this help
```

## Troubleshooting

**Empty batch log**: `claude -p` buffers output until completion. A large task may take several minutes. Check `ps aux | grep claude` to confirm it's still running.

**Conductor exits immediately**: Check `conductor.log` for the reason. Common causes: missing mission file, stop signal present, iteration limit already reached.

**Scores not updating**: The orchestrator must write to `conductor/state.json` before exiting. If it doesn't, the conductor re-seeds from findings on next run.

**Evaluator always rejects**: The evaluator needs real execution evidence (command + stdout). If the orchestrator only reads code without running tests, the evaluator will reject. This is by design.
