# /iterate — Sandbox iteration: select datasets, replay, score, diagnose, fix, repeat

You are in **Stage 2: SANDBOX ITERATION** (the inner loop). Your job is to improve the pipeline by replaying **datasets** and measuring improvement via **scoring**. This is where development happens.

Read the full stage protocol: `features/README.md` (section: Stage 2: SANDBOX ITERATION)
Read dataset structure: `features/README.md` (section: Datasets)
Read the glossary: `features/README.md` (section: Glossary)

## Your constraints

- Do NOT run live meetings — you are in the sandbox, work only with datasets
- Do NOT modify datasets — they are immutable records of what happened
- Do NOT add scenarios that aren't in any active dataset — if you need new scenarios, exit to `/expand`
- Do NOT skip scoring after a fix — every change must be measured
- Do NOT iterate without a control dataset — always replay at least one known-good dataset to catch regressions
- Do NOT change infra config (.env) — if infra needs to change, exit to `/env-setup`
- Follow diagnose → fix → verify → audit phase discipline within each iteration

## Startup: load context

### 1. Identify the feature

Determine which feature from the working directory or conversation context.

### 2. Inventory datasets

Read `features/{name}/tests/datasets/*/manifest.md`. For each dataset:

| Dataset ID | Status | Scenarios | Baseline | Infra compatible? |
|-----------|--------|-----------|---------- |-------------------|
| {id} | active/superseded/retired | {tags} | {X}% | yes/no |

Only `active` datasets are candidates for iteration.

### 3. Select datasets for this iteration

Based on what you're trying to fix:

**Target datasets** — contain the scenarios with errors you want to improve:
- Read `features/{name}/tests/findings.md` for current errors
- Match errors to scenario tags in dataset manifests
- Select the dataset(s) that cover those scenarios

**Control datasets** — contain scenarios that should NOT regress:
- Pick at least one dataset with known-good scoring
- If none exists, use the oldest stable dataset as control

Log: `SANDBOX: selected datasets — target: {id1} (scenarios: X, Y), control: {id2} (scenarios: Z)`

### 4. Verify infra matches

Compare `.env` against the **infra snapshots** in the selected datasets. All selected datasets must have compatible infra snapshots:
- Same MODEL_SIZE, COMPUTE_TYPE, pipeline params
- If incompatible → can't combine. Either pick one dataset or `/env-setup` to align.

### 5. Read current state

| File | What you learn |
|------|---------------|
| `features/{name}/tests/findings.md` | Last known scoring, known issues, certainty scores |
| Selected dataset manifests | Scenarios, baseline scoring, hypothesis |
| `features/{name}/.env` | Current infra config |

## Iteration loop

### 6. Replay and score

Run `make play-replay DATASET={id}` for each selected dataset.

Read the output. Extract per dataset:
- Overall accuracy (scoring %)
- Per-scenario breakdown
- Specific errors: which utterances lost, words misattributed, speakers wrong

Compare to the dataset's baseline in its manifest — are you above or below baseline?

### 7. Diagnose

For each error in the scoring output, trace the root cause through the pipeline:

| Symptom | Where to look |
|---------|--------------|
| Utterance lost entirely | Buffer flush logic, minAudioDuration threshold, idle timeout |
| Wrong speaker attributed | Speaker-mapper, caption boundary timing, caption delay |
| Text garbled or hallucinated | Confidence filters, Whisper quality signals, audio quality |
| Text truncated | Buffer trim, maxBufferDuration, segment confirmation logic |
| Duplicate segments | Confirmation threshold, dedup logic |

Read the relevant source code. Find the root cause, not the symptom.

### 8. Fix

Make the minimal code change to address the root cause. One fix per root cause:
- If it's a threshold: change the threshold, document why
- If it's logic: fix the logic, not the symptoms
- If it's a missing case: add the case

Do NOT stack workarounds. Do NOT fix things that aren't broken.

### 9. Replay and re-score ALL selected datasets

Run replay on both target and control datasets. Compare:

| Dataset | Scenario | Before | After | Delta |
|---------|----------|--------|-------|-------|
| {target} | {scenario} | X% | Y% | +Z% |
| {control} | {scenario} | X% | Y% | 0% (must not regress) |

**If control regresses** → the fix broke something. Revert or refine.
**If target improves and control holds** → good, continue.

Log: `SANDBOX: iteration {N} — {target-id}: {X}% → {Y}% | {control-id}: {X}% → {Y}% — fix: {description}`

### 10. Decide next step

**If scoring improved and more errors remain in current datasets** → go to step 7

**If scoring improved and target met across all active datasets** → exit to GATE:
- Update `findings.md` with final scoring per dataset
- All certainty scores >= 80?
- Log: `SANDBOX: target met — {id1}: {X}%, {id2}: {Y}%, all checks >= 80`

**If scoring did NOT improve for 3+ iterations** → check:
- Are the remaining errors in scenarios covered by your datasets?
  - YES → diagnosis is wrong, try a different root cause
  - NO → you've hit a **plateau**. Identify which scenarios are missing.
- Tell user to run `/expand`. Provide:
  - Current scoring per dataset per scenario
  - Which scenarios have residual errors
  - What new scenarios would help

Log: `SANDBOX: plateau — {id}: stuck at {X}% for {N} iterations — missing scenarios: {list}`

### 11. Update findings

After each meaningful iteration, update `features/{name}/tests/findings.md`:
- Current scoring per dataset per scenario
- What was fixed
- What errors remain
- Which datasets were used
- Plateau status

## Output format

After each iteration, report concisely:

```
Iteration {N}:
  {target-dataset}: {X}% → {Y}% ({+/-Z}%)
  {control-dataset}: {X}% → {Y}% ({+/-Z}%)
  Fix: {one-line description}
  Remaining: {count} errors in {scenarios}
  Status: {iterating | plateau | target met}
```
