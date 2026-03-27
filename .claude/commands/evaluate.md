# /evaluate — Run the skeptical evaluator on the latest batch

Review the last conductor batch for inflated claims, missing evidence, and regressions.

## Steps

### 1. Load context
```bash
cat conductor/mission.md
cat conductor/state.json
```

### 2. Find latest batch log
```bash
ls -t conductor/batches/batch-*.log | head -1
```
Read the latest batch log.

### 3. Check what changed
```bash
git log --oneline -5
git diff HEAD~1 -- features/*/tests/findings.md
```

### 4. For each feature that advanced

Read its `features/{name}/tests/findings.md`. Verify:
- Score claim has execution evidence (command + stdout)
- Evidence supports the claimed score
- No regressions in other features

### 5. Check score history for regressions
```bash
python3 conductor/check-completion.py --status
```

### 6. Write verdict

Write `conductor/evaluator-verdict.md` with the table of claims, verdicts, and evidence.

If REJECT: explain specifically what's missing or wrong.
If ACCEPT: explain what evidence confirms the claims.
