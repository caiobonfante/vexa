# /iterate — Sandbox iteration: replay, score, diagnose, fix, repeat

You are in **Stage 2: SANDBOX ITERATION** (the inner loop). Your job is to improve the pipeline by replaying collected data and measuring improvement via scoring. This is where development happens.

Read the full stage protocol: `features/README.md` (section: Stage 2: SANDBOX ITERATION)
Read the glossary: `features/README.md` (section: Glossary)

## Your constraints

- Do NOT run live meetings — you are in the sandbox, work only with collected data
- Do NOT modify ground truth or collected data — they are immutable records of what happened
- Do NOT add scenarios that aren't in the collected data — if you need new scenarios, exit to `/expand`
- Do NOT skip scoring after a fix — every change must be measured
- Do NOT change infra config (.env) — if infra needs to change, exit to `/env-setup`
- Follow diagnose → fix → verify → audit phase discipline within each iteration

## Startup: load context

### 1. Identify the feature

Determine which feature from the working directory or conversation context.

### 2. Read current state

Read these files to understand where you are:

| File | What you learn |
|------|---------------|
| `features/{name}/tests/findings.md` | Last known scoring, known issues, certainty scores |
| `features/{name}/tests/infra-snapshot.md` | What infra the collected data was captured with |
| `features/{name}/tests/README.md` | Current stage status, test approach, datasets |
| `features/{name}/.env` | Current infra config — must match infra snapshot |

### 3. Verify infra matches snapshot

Compare `.env` against the infra snapshot from the collection run. If they differ on any value that affects pipeline behavior (MODEL_SIZE, COMPUTE_TYPE, pipeline params), STOP:
- Flag the mismatch
- Tell user to run `/env-setup` to align infra
- Do not iterate with mismatched infra — scoring results would be invalid

### 4. Check collected data exists

Verify the test directory has:
- Ground truth file(s) — the script with timestamps
- Collected data files — audio, caption events, pipeline output
- A replay test that can consume them (`make play-replay` target in Makefile)

If any are missing → tell user to run `/collect` first.

## Iteration loop

### 5. Replay and score

Run `make play-replay` (or equivalent) from `features/{name}/tests/`.

Read the output. Extract:
- Overall accuracy (scoring %)
- Per-scenario breakdown if available
- Specific errors: which utterances were lost, which words were misattributed, which speakers were wrong

### 6. Diagnose

For each error in the scoring output, trace the root cause through the pipeline:

| Symptom | Where to look |
|---------|--------------|
| Utterance lost entirely | Buffer flush logic, minAudioDuration threshold, idle timeout |
| Wrong speaker attributed | Speaker-mapper, caption boundary timing, caption delay |
| Text garbled or hallucinated | Confidence filters, Whisper quality signals, audio quality |
| Text truncated | Buffer trim, maxBufferDuration, segment confirmation logic |
| Duplicate segments | Confirmation threshold, dedup logic |

Read the relevant source code. Find the root cause, not the symptom.

### 7. Fix

Make the minimal code change to address the root cause. One fix per root cause:
- If it's a threshold: change the threshold, document why
- If it's logic: fix the logic, not the symptoms
- If it's a missing case: add the case

Do NOT stack workarounds. Do NOT fix things that aren't broken.

### 8. Replay and re-score

Run `make play-replay` again. Compare:
- New scoring vs previous scoring
- Did the fix improve the target metric?
- Did anything regress?

Log the delta: `SANDBOX: iteration {N} — scoring: {X}% → {Y}% (delta: {+/-Z}%) — fix: {description}`

### 9. Decide next step

**If scoring improved and more errors remain** → go to step 6 (diagnose next error)

**If scoring improved and target met** → exit to GATE:
- Update `findings.md` with final scoring and certainty scores
- All certainty scores >= 80?
- Log: `SANDBOX: target met — scoring: {X}%, all certainty scores >= 80`

**If scoring did NOT improve for 3+ iterations** → you've hit a plateau:
- Identify which errors remain
- Determine which scenarios they're in
- Are these scenarios covered in the collected data?
  - YES → keep diagnosing, the fix isn't right yet
  - NO → exit to EXPAND: `SANDBOX: plateau reached — scoring stuck at {X}% for {N} iterations — need scenarios: {list}`
- Tell user to run `/expand`

### 10. Update findings

After each meaningful iteration (not every micro-change), update `features/{name}/tests/findings.md`:
- Current scoring
- What was fixed
- What errors remain
- Plateau status

## Output format

After each iteration, report concisely:

```
Iteration {N}: {X}% → {Y}% ({+/-Z}%)
Fix: {one-line description}
Remaining: {count} errors in {scenarios}
Status: {iterating | plateau | target met}
```
