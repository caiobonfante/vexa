#!/bin/bash
# =============================================================================
# CONDUCTOR — One command, one problem, walk away.
#
# Usage:
#   make conductor                  # or: ./conductor/run.sh
#   make conductor-status           # or: ./conductor/run.sh --status
#   make conductor-loop N=5         # or: ./conductor/run.sh --max-iterations 5
#
# The conductor:
#   1. Reads conductor/mission.md — your objective
#   2. Ensures conductor/state.json exists (seeds if needed)
#   3. Spawns claude orchestrator for one batch
#   4. Runs skeptical evaluator on batch claims
#   5. Takes score snapshot, checks for plateau
#   6. Checks mission completion
#   7. Loops until done, plateau, or limit hit
#
# All state lives in conductor/:
#   conductor/mission.md        — your steering wheel
#   conductor/state.json        — machine-readable state
#   conductor/conductor.log     — timeline of decisions
#   conductor/batches/          — full agent output per iteration
#   conductor/evaluator-verdict.md — latest evaluator verdict
# =============================================================================

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
CONDUCTOR_DIR="$REPO/conductor"
MISSION_FILE="$CONDUCTOR_DIR/mission.md"
STATE_FILE="$CONDUCTOR_DIR/state.json"
LOG_FILE="$CONDUCTOR_DIR/conductor.log"
CHECK_SCRIPT="$CONDUCTOR_DIR/check-completion.py"
VERDICT_FILE="$CONDUCTOR_DIR/evaluator-verdict.md"
BATCH_DIR="$CONDUCTOR_DIR/batches"
STOP_FILE="$CONDUCTOR_DIR/mission.stop"

# Defaults
MAX_ITERATIONS=10
PLATEAU_THRESHOLD=3
DRY_RUN=false
STATUS_ONLY=false
BUDGET_USD=""
MISSION_NAME=""
LIST_MISSIONS=false
MERGE_MISSION=""

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --mission|-m) MISSION_NAME="$2"; shift 2 ;;
    --max-iterations) MAX_ITERATIONS="$2"; shift 2 ;;
    --plateau-threshold) PLATEAU_THRESHOLD="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --status) STATUS_ONLY=true; shift ;;
    --budget) BUDGET_USD="$2"; shift 2 ;;
    --list) LIST_MISSIONS=true; shift ;;
    --merge) MERGE_MISSION="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: ./conductor/run.sh [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  -m, --mission NAME      Run in a git worktree (parallel-safe)"
      echo "  --max-iterations N      Max iterations (default: 10)"
      echo "  --plateau-threshold N   Unchanged iterations before plateau (default: 3)"
      echo "  --budget USD            Max spend per iteration (default: unlimited)"
      echo "  --dry-run               Seed state + show status, don't run"
      echo "  --status                Show current status"
      echo "  --list                  List active missions (worktrees)"
      echo "  -h, --help              Show this help"
      echo ""
      echo "Parallel missions:"
      echo "  ./conductor/run.sh -m chat-fix &"
      echo "  ./conductor/run.sh -m zoom-transcription &"
      echo "  ./conductor/run.sh --list"
      exit 0
      ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# -----------------------------------------------------------------------------
# Worktree-based parallel missions
# -----------------------------------------------------------------------------
WORKTREE_DIR="$REPO/.worktrees"

list_missions() {
  echo "=== Active Missions ==="
  if [[ ! -d "$WORKTREE_DIR" ]]; then
    echo "  (none)"
    return
  fi
  for wt in "$WORKTREE_DIR"/*/; do
    local name
    name=$(basename "$wt")
    if [[ -f "$wt/conductor/mission.md" ]]; then
      local focus
      focus=$(grep -i '^Focus:' "$wt/conductor/mission.md" 2>/dev/null | cut -d: -f2- | xargs)
      local state_status="unknown"
      if [[ -f "$wt/conductor/state.json" ]]; then
        state_status=$(python3 -c "
import json
state = json.loads(open('${wt}conductor/state.json').read())
print(f\"iter {state.get('iteration',0)}, {state.get('status','?')}\")
" 2>/dev/null || echo "?")
      fi
      local branch
      branch=$(git -C "$wt" branch --show-current 2>/dev/null || echo "?")
      echo "  $name — $focus [$state_status] (branch: $branch)"
    fi
  done
  echo ""
  echo "Worktrees:"
  git -C "$REPO" worktree list 2>/dev/null
}

setup_worktree() {
  local name="$1"
  local wt_path="$WORKTREE_DIR/$name"
  local branch="conductor/$name"

  if [[ -d "$wt_path" ]]; then
    echo "Worktree '$name' already exists at $wt_path"
    return 0
  fi

  mkdir -p "$WORKTREE_DIR"

  # Create branch from current HEAD if it doesn't exist
  if ! git -C "$REPO" rev-parse --verify "$branch" &>/dev/null; then
    git -C "$REPO" branch "$branch" HEAD
  fi

  git -C "$REPO" worktree add "$wt_path" "$branch"

  # Copy entire conductor/ directory into worktree (may not be committed yet)
  mkdir -p "$wt_path/conductor/batches"
  cp "$CONDUCTOR_DIR/run.sh" "$wt_path/conductor/run.sh"
  cp "$CONDUCTOR_DIR/check-completion.py" "$wt_path/conductor/check-completion.py"
  cp "$CONDUCTOR_DIR/Makefile" "$wt_path/conductor/Makefile"
  chmod +x "$wt_path/conductor/run.sh" "$wt_path/conductor/check-completion.py"

  # Copy mission file: prefer conductor/missions/{name}.md, fall back to conductor/mission.md
  local mission_source="$CONDUCTOR_DIR/missions/${name}.md"
  if [[ -f "$mission_source" ]]; then
    cp "$mission_source" "$wt_path/conductor/mission.md"
    echo "Mission loaded from: missions/${name}.md"
  elif [[ -f "$MISSION_FILE" ]]; then
    cp "$MISSION_FILE" "$wt_path/conductor/mission.md"
    echo "Mission loaded from: mission.md (default)"
  else
    echo "ERROR: No mission file found. Create conductor/missions/${name}.md first."
    echo ""
    echo "  cat > conductor/missions/${name}.md << 'EOF'"
    echo "  # Mission"
    echo "  Focus: <feature name>"
    echo "  Problem: <what's broken>"
    echo "  Target: <definition of done>"
    echo "  Stop-when: target met OR 5 iterations"
    echo "  Constraint: none"
    echo "  EOF"
    git -C "$REPO" worktree remove "$wt_path" --force 2>/dev/null
    git -C "$REPO" branch -D "$branch" 2>/dev/null
    return 1
  fi

  # Copy .claude agent/command configs if not in worktree
  if [[ ! -f "$wt_path/.claude/agents/evaluator.md" ]]; then
    mkdir -p "$wt_path/.claude/agents" "$wt_path/.claude/commands"
    cp "$REPO/.claude/agents/evaluator.md" "$wt_path/.claude/agents/" 2>/dev/null || true
    cp "$REPO/.claude/commands/conductor-entry.md" "$wt_path/.claude/commands/" 2>/dev/null || true
    cp "$REPO/.claude/commands/evaluate.md" "$wt_path/.claude/commands/" 2>/dev/null || true
  fi

  echo "Worktree created: $wt_path (branch: $branch)"
}

run_in_worktree() {
  local name="$1"
  local wt_path="$WORKTREE_DIR/$name"

  setup_worktree "$name"

  # Re-exec this script inside the worktree (without --mission to avoid recursion)
  local args=()
  [[ $MAX_ITERATIONS -ne 10 ]] && args+=(--max-iterations "$MAX_ITERATIONS")
  [[ $PLATEAU_THRESHOLD -ne 3 ]] && args+=(--plateau-threshold "$PLATEAU_THRESHOLD")
  [[ -n "$BUDGET_USD" ]] && args+=(--budget "$BUDGET_USD")
  [[ "$DRY_RUN" == "true" ]] && args+=(--dry-run)
  [[ "$STATUS_ONLY" == "true" ]] && args+=(--status)

  cd "$wt_path"
  exec "$wt_path/conductor/run.sh" "${args[@]}"
}

merge_worktree() {
  local name="$1"
  local wt_path="$WORKTREE_DIR/$name"
  local branch="conductor/$name"

  if [[ ! -d "$wt_path" ]]; then
    echo "No worktree '$name' to merge"
    return 1
  fi

  # Collect changed files upfront
  local changed_files=""
  # Uncommitted changes
  changed_files=$(git -C "$wt_path" diff --name-only HEAD 2>/dev/null || true)
  # Plus committed changes vs main branch
  local committed_files
  committed_files=$(git -C "$REPO" diff --name-only "HEAD...$branch" 2>/dev/null || true)
  if [[ -n "$committed_files" ]]; then
    changed_files=$(printf "%s\n%s" "$changed_files" "$committed_files" | sort -u | grep -v '^$' || true)
  fi

  # No changes = nothing to merge
  if [[ -z "$changed_files" ]]; then
    echo "No changes in worktree '$name'. Nothing to merge."
    echo ""
    echo "Clean up worktree? Run: git worktree remove .worktrees/$name"
    return 0
  fi

  echo "═══ Pre-merge gate: $name ═══"
  echo ""
  echo "Changed files:"
  echo "$changed_files" | sed 's/^/  /'
  echo ""
  local gate_pass=true

  # 1. Check evaluator verdict
  echo "1. Evaluator verdict..."
  local verdict_file="$wt_path/conductor/evaluator-verdict.md"
  if [[ -f "$verdict_file" ]]; then
    if grep -qi "REJECT" "$verdict_file"; then
      echo "   FAIL: evaluator REJECTED the last batch"
      echo "   $(grep -i 'reject' "$verdict_file" | head -3)"
      gate_pass=false
    else
      echo "   PASS: evaluator accepted"
    fi
  else
    echo "   WARN: no evaluator verdict found (evaluator didn't run?)"
  fi

  # 2. Check mission focus
  echo "2. Mission focus..."
  local focus=""
  if [[ -f "$wt_path/conductor/mission.md" ]]; then
    focus=$(grep -i '^Focus:' "$wt_path/conductor/mission.md" 2>/dev/null | cut -d: -f2- | xargs)
  fi
  if [[ -n "$focus" ]]; then
    echo "   PASS: focus=$focus"
  else
    echo "   WARN: no focus in mission.md"
  fi

  # 3. Check manifest constraints — look for cross-service imports
  echo "3. Manifest constraints..."
  if [[ -n "$focus" && -f "$REPO/features/$focus/README.md" ]]; then
    local violations=0
    # Check: no cross-service Python imports
    local changed_py
    changed_py=$(echo "$changed_files" | grep '\.py$' | head -20)
    if [[ -n "$changed_py" ]]; then
      for f in $changed_py; do
        if [[ -f "$wt_path/$f" ]]; then
          # Check for imports from other services/
          local service_dir
          service_dir=$(echo "$f" | grep -o 'services/[^/]*' | head -1)
          if [[ -n "$service_dir" ]]; then
            local cross_imports
            cross_imports=$(grep -n "from services\.\|import services\." "$wt_path/$f" 2>/dev/null | grep -v "$service_dir" || true)
            if [[ -n "$cross_imports" ]]; then
              echo "   FAIL: cross-service import in $f"
              echo "   $cross_imports"
              violations=$((violations + 1))
            fi
          fi
        fi
      done
    fi
    if [[ $violations -eq 0 ]]; then
      echo "   PASS: no constraint violations detected"
    else
      echo "   FAIL: $violations constraint violation(s)"
      gate_pass=false
    fi
  else
    echo "   SKIP: no manifest found for focus '$focus'"
  fi

  # 4. Check tests pass
  echo "4. Tests..."
  if [[ -n "$focus" ]]; then
    # Try to find and run the feature's tests
    local test_dir="$wt_path/features/$focus/tests"
    local service_tests=""
    # Find test files related to focus
    if [[ -d "$test_dir" ]]; then
      local test_scripts
      test_scripts=$(find "$test_dir" -name "*.sh" -o -name "test_*.py" 2>/dev/null | head -5)
      if [[ -n "$test_scripts" ]]; then
        echo "   Found test scripts in $test_dir"
        # Run Python tests if they exist
        local py_tests
        py_tests=$(find "$test_dir" -name "test_*.py" 2>/dev/null | head -3)
        if [[ -n "$py_tests" ]]; then
          if python3 -m pytest "$test_dir" -q --tb=no 2>/dev/null; then
            echo "   PASS: pytest passed"
          else
            echo "   FAIL: pytest failed"
            gate_pass=false
          fi
        else
          echo "   SKIP: no pytest files, manual test scripts only"
        fi
      else
        echo "   SKIP: no test scripts found"
      fi
    else
      echo "   SKIP: no test directory at $test_dir"
    fi
  else
    echo "   SKIP: no focus to determine tests"
  fi

  # 5. Check for regressions — reseed scores and compare
  echo "5. Regression check..."
  local pre_scores post_scores
  pre_scores=$(python3 "$CONDUCTOR_DIR/check-completion.py" --status --state "$CONDUCTOR_DIR/state.json" 2>/dev/null | grep -E "^\s+\S+\s+[0-9]+" || true)
  # Reseed from worktree findings to get post-scores
  post_scores=$(cd "$wt_path" && python3 "$CONDUCTOR_DIR/check-completion.py" --status 2>/dev/null | grep -E "^\s+\S+\s+[0-9]+" || true)
  if [[ -n "$pre_scores" && -n "$post_scores" ]]; then
    local regressions
    regressions=$(python3 -c "
pre = {}
post = {}
for line in '''$pre_scores'''.strip().split('\n'):
    parts = line.split()
    if len(parts) >= 2:
        pre[parts[0]] = int(parts[1])
for line in '''$post_scores'''.strip().split('\n'):
    parts = line.split()
    if len(parts) >= 2:
        post[parts[0]] = int(parts[1])
regs = []
for name, score in pre.items():
    if name in post and post[name] < score:
        regs.append(f'{name}: {score} -> {post[name]}')
if regs:
    print('\n'.join(regs))
" 2>/dev/null || true)
    if [[ -n "$regressions" ]]; then
      echo "   WARN: score regressions detected:"
      echo "$regressions" | sed 's/^/     /'
    else
      echo "   PASS: no regressions"
    fi
  else
    echo "   SKIP: couldn't compare scores"
  fi

  echo ""

  # Gate verdict
  if [[ "$gate_pass" == "false" ]]; then
    echo "═══ MERGE BLOCKED: pre-merge gate FAILED ═══"
    echo ""
    echo "Fix the failures above, then retry: ./conductor/run.sh --merge $name"
    return 1
  fi

  echo "═══ Pre-merge gate PASSED ═══"
  echo ""

  # Check if there are changes to merge
  local commits
  commits=$(git -C "$REPO" log "HEAD..$branch" --oneline 2>/dev/null)
  local uncommitted
  uncommitted=$(git -C "$wt_path" diff --stat HEAD 2>/dev/null)

  # Commit any uncommitted changes in worktree first
  if [[ -n "$uncommitted" ]]; then
    echo "Committing uncommitted changes in worktree..."
    git -C "$wt_path" add -A
    git -C "$wt_path" commit -m "conductor($name): uncommitted changes from mission run"
  fi

  commits=$(git -C "$REPO" log "HEAD..$branch" --oneline 2>/dev/null)
  if [[ -z "$commits" ]]; then
    echo "No commits to merge from $name"
  else
    echo "Commits to merge:"
    echo "$commits" | sed 's/^/  /'
    echo ""
    echo "Merging $branch into $(git -C "$REPO" branch --show-current)..."
    git -C "$REPO" merge "$branch" --no-edit
    echo "Merged."
  fi

  # Clean up
  git -C "$REPO" worktree remove "$wt_path" 2>/dev/null || true
  git -C "$REPO" branch -d "$branch" 2>/dev/null || true
  echo "Worktree '$name' cleaned up."
}

# Handle --list
if [[ "$LIST_MISSIONS" == "true" ]]; then
  list_missions
  exit 0
fi

# Handle --merge
if [[ -n "$MERGE_MISSION" ]]; then
  merge_worktree "$MERGE_MISSION"
  exit $?
fi

# Handle --mission: delegate to worktree
if [[ -n "$MISSION_NAME" ]]; then
  if [[ "$STATUS_ONLY" == "true" ]]; then
    wt_path="$WORKTREE_DIR/$MISSION_NAME"
    if [[ -f "$wt_path/conductor/run.sh" ]]; then
      exec "$wt_path/conductor/run.sh" --status
    else
      echo "No worktree '$MISSION_NAME'. Use --list to see active missions."
      exit 1
    fi
  fi
  run_in_worktree "$MISSION_NAME"
  exit $?
fi

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
log() {
  local msg="[$(date -Is)] CONDUCTOR: $1"
  echo "$msg"
  echo "$msg" >> "$LOG_FILE"
}

# -----------------------------------------------------------------------------
# Preflight
# -----------------------------------------------------------------------------
preflight() {
  if ! command -v claude &>/dev/null; then
    echo "ERROR: claude CLI not found. Install: npm install -g @anthropic-ai/claude-code"
    exit 1
  fi

  if [[ ! -f "$MISSION_FILE" ]]; then
    echo "ERROR: No mission file at $MISSION_FILE"
    echo "Create one:"
    echo ""
    echo "  cat > conductor/mission.md << 'EOF'"
    echo "  # Mission"
    echo "  Focus: <what to work on>"
    echo "  Problem: <what's broken>"
    echo "  Target: <definition of done>"
    echo "  Stop-when: target met OR 5 iterations"
    echo "  Constraint: none"
    echo "  EOF"
    exit 1
  fi

  mkdir -p "$BATCH_DIR"

  if [[ ! -f "$STATE_FILE" ]]; then
    log "No state file — seeding from current findings"
    python3 "$CHECK_SCRIPT" --seed --state "$STATE_FILE" --mission "$MISSION_FILE"
    log "State seeded: $STATE_FILE"
  fi
}

# -----------------------------------------------------------------------------
# Build the orchestrator prompt
# -----------------------------------------------------------------------------
build_prompt() {
  local mission
  mission=$(cat "$MISSION_FILE")

  # Check if evaluator rejected last iteration
  local rejection_context=""
  local last_eval
  last_eval=$(python3 -c "
import json
from pathlib import Path
state = json.loads(Path('$STATE_FILE').read_text())
print(state.get('last_evaluation', 'none'))
" 2>/dev/null || echo "none")

  if [[ "$last_eval" == "rejected" ]]; then
    local eval_detail
    eval_detail=$(python3 -c "
import json
from pathlib import Path
state = json.loads(Path('$STATE_FILE').read_text())
print(state.get('evaluation_context', 'No details'))
" 2>/dev/null || echo "No details")
    rejection_context="
## EVALUATOR REJECTION

The skeptical evaluator REJECTED the previous iteration's claims:

$eval_detail

You MUST address these rejections in this iteration. Provide the missing evidence or correct the inflated scores.
"
  fi

  # Check if force_strategy is set (plateau detected)
  local plateau_context=""
  local force_strategy
  force_strategy=$(python3 -c "
import json
from pathlib import Path
state = json.loads(Path('$STATE_FILE').read_text())
print(state.get('force_strategy', False))
" 2>/dev/null || echo "False")

  if [[ "$force_strategy" == "True" ]]; then
    plateau_context="
## PLATEAU ALERT

Scores have not improved for multiple iterations. The current approach is not working.
Before executing, STOP and reassess:
1. Read the experiment ledger — has this approach been tried before?
2. Try a DIFFERENT root cause hypothesis
3. If the blocker is infrastructure you can't fix, document it clearly and pivot
4. Consider whether the mission scope needs narrowing

After this iteration, force_strategy will be cleared.
"
    python3 -c "
import json
from pathlib import Path
state_path = Path('$STATE_FILE')
state = json.loads(state_path.read_text())
state['force_strategy'] = False
state_path.write_text(json.dumps(state, indent=2) + '\n')
" 2>/dev/null
  fi

  cat <<PROMPT
You are the features-orchestrator lead. Your operating manual is features/.claude/CLAUDE.md.
$rejection_context
$plateau_context

## YOUR MISSION (from conductor/mission.md)

$mission

## ENTRY PROTOCOL (mandatory, in order)

1. cat conductor/state.json
2. cat conductor/mission.md
3. cat features/tests/findings.md
4. cat features/orchestrator-log.md
5. cat features/tools/README.md
6. git log --oneline -10

## EXECUTION

Your mission comes from the mission file above. Execute:

1. DIAGNOSE: What's broken? Trace the full chain relevant to the mission.
   Follow the diagnostic protocol from .claude/agents.md.
   Check services, endpoints, UI, logs. Fail fast — test the riskiest thing first.

2. FIX: Minimal changes to fix root causes. One fix per root cause.
   Don't stack workarounds. Don't fix things outside the mission scope.

3. VERIFY: Prove it works. For UI/dashboard missions, verify in a real browser
   (use the /deliver protocol). For API missions, show curl/test output.
   Evidence must be specific: command + stdout + result.

4. UPDATE FINDINGS: Write execution evidence to features/{focus}/tests/findings.md.
   Every score claim must have: command run + stdout captured. No prose-only claims.

5. UPDATE README: The feature's README.md must be honest about current state:
   - Quality Bar: change FAIL → PASS only where you have execution evidence
   - Certainty: update scores + evidence + date
   - Known Issues: add anything discovered, remove anything fixed
   - Data Flow: update ONLY if the architecture actually changed
   - Why / Constraints: do NOT change unless the mission explicitly requires it
   README is the source of truth. If code changed behavior, README must reflect it.

6. UPDATE STATE: Update conductor/state.json with new scores.
   Append to features/orchestrator-log.md what you did and what changed.

## RULES

- Do NOT ask the human anything. You are autonomous.
- Do NOT stop until the mission target is verified OR you hit an infra blocker you cannot fix.
- Spawn teams (executor + verifier) when the fix requires multiple services. Don't solo everything.
- Write ALL state to files before exiting. The next session reads files, not context.
- If you hit a blocker you can't resolve, write it to findings and exit with a clear explanation.
- README quality bar items stay FAIL until proven with evidence. No optimistic updates.
- Never change README constraints or data flow unless the mission explicitly targets architecture changes.
PROMPT
}

# -----------------------------------------------------------------------------
# Run one iteration
# -----------------------------------------------------------------------------
run_iteration() {
  local iteration=$1
  local batch_log="$BATCH_DIR/batch-${iteration}.log"

  log "iteration $iteration — spawning orchestrator"

  # Update state
  python3 -c "
import json
from pathlib import Path
state_path = Path('$STATE_FILE')
state = json.loads(state_path.read_text())
state['iteration'] = $iteration
state['last_batch'] = '$(date -Is)'
state['status'] = 'running'
state_path.write_text(json.dumps(state, indent=2) + '\n')
"

  # Build prompt file: orchestrator instructions + feature README + owned service READMEs
  local prompt_file="$BATCH_DIR/prompt-${iteration}.txt"
  build_prompt > "$prompt_file"

  # Append feature README as system design context
  local focus
  focus=$(grep -i '^Focus:' "$MISSION_FILE" 2>/dev/null | cut -d: -f2- | xargs)
  if [[ -n "$focus" ]]; then
    local feature_readme="$REPO/features/$focus/README.md"
    if [[ -f "$feature_readme" ]]; then
      echo "" >> "$prompt_file"
      echo "## FEATURE SYSTEM DESIGN (from features/$focus/README.md)" >> "$prompt_file"
      echo "" >> "$prompt_file"
      cat "$feature_readme" >> "$prompt_file"
    fi

    # Extract code ownership dirs from feature README, append their READMEs
    local owned_dirs
    owned_dirs=$(grep -E '^\s*(services|packages|libs)/' "$feature_readme" 2>/dev/null | sed 's/→.*//' | xargs 2>/dev/null || true)
    for dir in $owned_dirs; do
      # Strip trailing whitespace and path suffixes like (bot-manager routes)
      dir=$(echo "$dir" | sed 's/(.*//' | xargs)
      local svc_readme="$REPO/$dir/README.md"
      if [[ -f "$svc_readme" ]]; then
        echo "" >> "$prompt_file"
        echo "## SERVICE DESIGN: $dir (from $dir/README.md)" >> "$prompt_file"
        echo "" >> "$prompt_file"
        cat "$svc_readme" >> "$prompt_file"
      fi
    done
  fi

  log "prompt built: $(wc -c < "$prompt_file") bytes, focus=$focus"

  # Run claude with prompt from file
  set +e
  local budget_flag=""
  if [[ -n "$BUDGET_USD" ]]; then
    budget_flag="--max-budget-usd $BUDGET_USD"
  fi
  local batch_stream="$BATCH_DIR/stream-${iteration}.jsonl"
  local batch_meta="$BATCH_DIR/meta-${iteration}.json"

  # Run claude with stream-json — every tool call, edit, bash command is an event
  claude -p "Execute the mission. Read conductor/mission.md and conductor/state.json first." \
    --append-system-prompt-file "$prompt_file" \
    --permission-mode auto \
    --output-format stream-json \
    --verbose \
    $budget_flag \
    > "$batch_stream" 2>&1
  local exit_code=$?
  set -e

  # Parse stream into human-readable activity log + metadata
  python3 "$CONDUCTOR_DIR/parse-stream.py" "$batch_stream" "$batch_log" "$batch_meta" "$iteration"

  log "batch output: $batch_log (exit: $exit_code, cost: $(python3 -c "import json; print(f\"\${json.loads(open('$batch_meta').read()).get('cost_usd',0):.2f}\")" 2>/dev/null || echo '?'))"

  # Update state status
  python3 -c "
import json
from pathlib import Path
state_path = Path('$STATE_FILE')
state = json.loads(state_path.read_text())
state['status'] = 'iteration_complete'
state_path.write_text(json.dumps(state, indent=2) + '\n')
"

  return $exit_code
}

# -----------------------------------------------------------------------------
# Run the skeptical evaluator
# -----------------------------------------------------------------------------
run_evaluator() {
  local iteration=$1

  log "iteration $iteration — running skeptical evaluator"

  local eval_prompt_file="$BATCH_DIR/eval-prompt-${iteration}.txt"
  cat > "$eval_prompt_file" <<'EVALPROMPT'
You are the skeptical evaluator. Read .claude/agents/evaluator.md for your full protocol.

Review the LATEST conductor batch. Check every score claim for:
1. Did the score actually move? (git diff findings.md)
2. Is there execution evidence? (command + stdout, not just code review)
3. Did anything regress? (compare score snapshots)
4. Is the team celebrating prematurely? (mock vs real, curl vs browser)

Write your verdict to conductor/evaluator-verdict.md.

Be skeptical. Rejection requires evidence. Confirmation also requires evidence.
Do NOT fix anything. Only verify and document.
EVALPROMPT

  local eval_log="$BATCH_DIR/eval-${iteration}.log"
  local eval_stream="$BATCH_DIR/eval-stream-${iteration}.jsonl"
  local eval_meta="$BATCH_DIR/eval-meta-${iteration}.json"

  set +e
  claude -p "Evaluate the latest conductor batch." \
    --append-system-prompt-file "$eval_prompt_file" \
    --agent evaluator \
    --permission-mode auto \
    --output-format stream-json \
    --verbose \
    > "$eval_stream" 2>&1
  local exit_code=$?

  # Parse stream into activity log + metadata
  python3 "$CONDUCTOR_DIR/parse-stream.py" "$eval_stream" "$eval_log" "$eval_meta" "$iteration"
  set -e

  log "evaluator output: $eval_log"

  # Check verdict
  if [[ -f "$VERDICT_FILE" ]]; then
    if grep -qi "REJECT" "$VERDICT_FILE"; then
      log "EVALUATOR REJECTED iteration $iteration claims"
      python3 -c "
import json
from pathlib import Path
state_path = Path('$STATE_FILE')
state = json.loads(state_path.read_text())
state['last_evaluation'] = 'rejected'
state['evaluation_context'] = Path('$VERDICT_FILE').read_text()[:500]
state_path.write_text(json.dumps(state, indent=2) + '\n')
"
      return 1
    else
      log "EVALUATOR ACCEPTED iteration $iteration claims"
      python3 -c "
import json
from pathlib import Path
state_path = Path('$STATE_FILE')
state = json.loads(state_path.read_text())
state['last_evaluation'] = 'accepted'
state.pop('evaluation_context', None)
state_path.write_text(json.dumps(state, indent=2) + '\n')
"
      return 0
    fi
  else
    log "EVALUATOR produced no verdict file — treating as accepted"
    return 0
  fi
}

# -----------------------------------------------------------------------------
# Check if we should stop
# -----------------------------------------------------------------------------
check_done() {
  python3 "$CHECK_SCRIPT" --check --state "$STATE_FILE" --mission "$MISSION_FILE" 2>/dev/null
  return $?
}

# =============================================================================
# MAIN
# =============================================================================
main() {
  preflight

  # Status only
  if [[ "$STATUS_ONLY" == "true" ]]; then
    python3 "$CHECK_SCRIPT" --status --state "$STATE_FILE" --mission "$MISSION_FILE"
    exit 0
  fi

  # Dry run
  if [[ "$DRY_RUN" == "true" ]]; then
    log "DRY RUN — checking current state"
    python3 "$CHECK_SCRIPT" --status --state "$STATE_FILE" --mission "$MISSION_FILE"
    exit 0
  fi

  # Check for stop signal
  if [[ -f "$STOP_FILE" ]]; then
    log "Stop signal found ($STOP_FILE). Remove it to continue."
    exit 0
  fi

  log "========================================"
  log "CONDUCTOR START"
  log "  mission: $(head -5 "$MISSION_FILE" | grep -i 'focus:' | cut -d: -f2- | xargs)"
  log "  max_iterations: $MAX_ITERATIONS"
  log "  plateau_threshold: $PLATEAU_THRESHOLD"
  if [[ -n "$BUDGET_USD" ]]; then
    log "  budget: \$$BUDGET_USD per iteration"
  else
    log "  budget: unlimited"
  fi
  log "========================================"

  # Take initial snapshot
  python3 "$CHECK_SCRIPT" --snapshot --state "$STATE_FILE" >/dev/null

  local iteration=0

  while [[ $iteration -lt $MAX_ITERATIONS ]]; do
    iteration=$((iteration + 1))

    # Check stop signal
    if [[ -f "$STOP_FILE" ]]; then
      log "Stop signal found. Halting."
      rm -f "$STOP_FILE"
      break
    fi

    # Re-read mission (allows live steering)
    if [[ ! -f "$MISSION_FILE" ]]; then
      log "Mission file removed. Halting."
      break
    fi

    # Check for plateau
    if [[ $iteration -gt 1 ]]; then
      local plateau_status
      plateau_status=$(python3 "$CHECK_SCRIPT" --plateau-check --plateau-threshold "$PLATEAU_THRESHOLD" --state "$STATE_FILE" 2>/dev/null || echo "ok")
      if [[ "$plateau_status" == "plateau" ]]; then
        log "PLATEAU DETECTED — scores unchanged for $PLATEAU_THRESHOLD iterations"
        python3 -c "
import json
from pathlib import Path
state_path = Path('$STATE_FILE')
state = json.loads(state_path.read_text())
state['force_strategy'] = True
state['plateau_counter'] = state.get('plateau_counter', 0) + 1
state_path.write_text(json.dumps(state, indent=2) + '\n')
"
      fi
    fi

    # Run one iteration
    run_iteration "$iteration"

    # Take score snapshot
    python3 "$CHECK_SCRIPT" --snapshot --state "$STATE_FILE" >/dev/null
    log "Score snapshot taken after iteration $iteration"

    # Run evaluator
    if run_evaluator "$iteration"; then
      log "Evaluation passed for iteration $iteration"
    else
      log "Evaluation REJECTED for iteration $iteration — next iteration will address rejections"
    fi

    # Check completion
    if check_done; then
      log "MISSION ACCOMPLISHED after $iteration iteration(s)"
      python3 -c "
import json
from pathlib import Path
state_path = Path('$STATE_FILE')
state = json.loads(state_path.read_text())
state['status'] = 'completed'
state_path.write_text(json.dumps(state, indent=2) + '\n')
"
      break
    fi

    log "Mission not yet met. Iteration $iteration/$MAX_ITERATIONS done."
  done

  if [[ $iteration -ge $MAX_ITERATIONS ]]; then
    log "Iteration limit reached ($MAX_ITERATIONS)."
  fi

  log "CONDUCTOR END"
  log "========================================"

  # Final status
  python3 "$CHECK_SCRIPT" --status --state "$STATE_FILE" --mission "$MISSION_FILE" --plateau-threshold "$PLATEAU_THRESHOLD"
}

main "$@"
