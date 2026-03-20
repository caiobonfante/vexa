# /expand — Design new scenarios and collection manifest after hitting a plateau

You are in **Stage 3: EXPAND**. Your job is to figure out what data you need next, design scenarios that target known weaknesses, and produce a collection manifest for the next collection run. You are planning, not executing.

Read the full stage protocol: `features/README.md` (section: Stage 3: EXPAND)
Read the glossary: `features/README.md` (section: Glossary)

## Your constraints

- Do NOT guess what data you need — base scenario design on specific errors from findings
- Do NOT design scenarios you can't score — every scenario needs a clear expected output
- Do NOT combine too many new scenarios in one script — isolate variables
- Do NOT skip the hypothesis — if you don't know why you're collecting, the data is wasted
- Do NOT skip control scenarios — include scenarios that already work to catch regressions
- Do NOT run live meetings or change code — you are planning, not executing

## Procedure

### 1. Read findings

Read `features/{name}/tests/findings.md` and `features/{name}/tests/README.md`.

Extract:
- Current scoring (the plateau number)
- Which specific errors remain (list each one)
- Which scenarios those errors occur in
- What the root cause diagnosis was from the last iteration

### 2. Read existing collected data inventory

What data do you already have? Read the collected data section in the test README:
- Which scenarios are covered?
- How many utterances per scenario?
- Which scenarios had good scoring vs bad?

### 3. Gap analysis

For each remaining error, determine:

| Error | Root cause | Scenario needed | Already have data? |
|-------|-----------|----------------|-------------------|
| {error 1} | {cause} | {scenario} | yes/no |
| {error 2} | {cause} | {scenario} | yes/no |

Errors where "Already have data?" = yes → these should have been fixed in sandbox iteration. If they weren't, the diagnosis might be wrong. Flag this.

Errors where "Already have data?" = no → these need new scenarios. These drive the collection manifest.

### 4. Formulate hypothesis

For each new scenario needed, write a testable hypothesis:

```
Hypothesis: {what you believe is happening}
Test: {what the scenario will measure}
Expected outcome: {if hypothesis is correct, scoring should show X}
Alternative: {if hypothesis is wrong, scoring will show Y instead}
```

The hypothesis must be falsifiable. "We need more data" is not a hypothesis. "Short phrases are lost because minAudioDuration=3s prevents submission of sub-1s utterances, and lowering the threshold to 0.5s will recover them" is.

### 5. Design scenarios

For each new scenario:

| Scenario name | What it isolates | Utterances needed | Expected behavior |
|---------------|-----------------|-------------------|-------------------|
| {name} | {one variable} | {count, duration} | {what correct output looks like} |

Design rules:
- **Isolate one variable per scenario.** Don't test short phrases AND overlaps in the same scenario — you won't know which caused the error.
- **Include controls.** Reuse 2-3 scenarios from previous scripts that had good scoring. If controls regress, you broke something.
- **Be specific about scoring.** "Word-level accuracy" is too vague. "12/12 single-word utterances attributed to correct speaker" is testable.
- **Consider platform behavior.** Will the platform (Teams, GMeet) behave differently for this scenario? Check caption behavior docs.

### 6. Write the script

Design the full script — every utterance, speaker, timing:

| # | Speaker | Utterance | Timing | Scenario | Notes |
|---|---------|-----------|--------|----------|-------|
| 1 | Alice | "..." | T+0s | control-normal-turns | Control from previous run |
| 2 | Bob | "..." | T+12s | control-normal-turns | |
| ... | | | | | |
| 8 | Alice | "Yes." | T+45s | short-phrase | New: sub-1s utterance |
| 9 | Bob | "OK." | T+47s | short-phrase | New: followed by speaker change |

Timing rules:
- Leave enough gap between scenarios so they don't interfere
- Keep the total script under 3 minutes (longer = more can go wrong)
- Put controls first (warm up), new scenarios after

### 7. Write the collection manifest

Produce the full manifest using the template from `features/README.md` (Stage 1: COLLECTION RUN). Every section must be filled:

1. **Why this collection run** — link to the plateau, cite scoring numbers
2. **Hypothesis** — from step 4
3. **Script** — from step 6
4. **Scenarios covered** — from step 5, including controls
5. **Infra requirements** — what `.env` values are needed? Usually same as previous run unless testing a config change
6. **Data to capture** — every data type, source, format. Include anything new that previous runs didn't capture.
7. **Capture checklist** — how to verify each data source is logging
8. **Replay readiness** — how the sandbox will consume this data. Will existing replay tests work or do they need modification?

Save the manifest as `features/{name}/tests/collection-manifest-{date}.md`

### 8. Review and report

Present to the user:
- The gap analysis (what errors, what scenarios needed)
- The hypothesis (what you're testing)
- The script (what bots will say)
- The manifest (complete plan)

Ask the user to review before proceeding to collection:
- Are the scenarios right?
- Is the hypothesis plausible?
- Is anything missing from the data capture plan?
- Does the infra need changes? If yes → `/env-setup` first, then `/collect`
- If infra is fine → `/collect`

Log: `EXPAND: manifest ready — scenarios: {list} — hypothesis: {description}`
