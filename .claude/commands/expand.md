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

### 2. Inventory existing datasets

Read all dataset manifests in `features/{name}/tests/datasets/*/manifest.md`.

Build a coverage map:

| Dataset ID | Status | Scenarios | Last scoring | Infra |
|-----------|--------|-----------|-------------|-------|
| {id} | active/superseded/retired | {tags} | {X}% | {model, compute} |

For each scenario tag across all active datasets:
- How many utterances cover it?
- What's the best scoring achieved?
- Is more data needed (e.g., only 2 utterances for a scenario vs 10)?
- Could a longer meeting provide better data (more context for Whisper)?

### 3. Gap analysis

For each remaining error, determine:

| Error | Root cause | Scenario needed | Covered by dataset? | Enough data? |
|-------|-----------|----------------|--------------------|--------------------|
| {error 1} | {cause} | {scenario} | {id} or none | yes / no — need more |
| {error 2} | {cause} | {scenario} | none | no |

Three cases:
- **Scenario covered, enough data, still failing** → diagnosis is wrong. Go back to sandbox iteration with a different approach. Flag this.
- **Scenario covered, not enough data** → need a bigger collection (longer meeting, more utterances). The new dataset should have more instances of this scenario.
- **Scenario not covered** → need a new scenario. This drives the collection manifest.

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
- Keep the total script under 3 minutes unless a longer meeting is specifically needed (e.g., testing buffer behavior over time)
- Put controls first (warm up), new scenarios after

### 6b. Consider dataset size

Sometimes the gap isn't a missing scenario but insufficient data for an existing one:
- **Need more instances** — 2 short-phrase utterances isn't enough to measure. Design 10+.
- **Need longer meetings** — buffer/confirmation behavior may differ at minute 1 vs minute 10. Design a 5+ minute script.
- **Need more speakers** — 3-speaker data can't test 5-speaker dynamics.

If the existing dataset has the right scenarios but not enough data, the new dataset should be a larger version, not a different one. After collection, mark the old dataset as `superseded by {new-id}`.

### 7. Write the collection manifest (becomes the dataset manifest)

Produce the full manifest using the **dataset manifest** template from `features/README.md` (section: Datasets). This manifest will be copied directly into the new dataset directory during `/collect`. Every section must be filled:

1. **Dataset ID** — `{platform}-{N}sp-{scenario-tag}-{YYYYMMDD}`
2. **Why this collection run** — link to the plateau, cite scoring numbers per dataset per scenario
3. **Hypothesis** — from step 4
4. **Script** — from step 6
5. **Scenarios covered** — from step 5, with tags, including controls
6. **Infra requirements** — what `.env` values are needed? Must be compatible with existing datasets you want to combine with.
7. **Data to capture** — every data type, source, format. Include anything new that previous runs didn't capture.
8. **Capture checklist** — how to verify each data source is logging
9. **Replay readiness** — how the sandbox will consume this dataset. Will existing replay tests work or do they need modification? Can this dataset be combined with existing ones?
10. **Relationship to existing datasets** — which existing datasets does this complement? supersede? Is the infra compatible for combining?

Save the manifest as `features/{name}/tests/collection-manifest-{date}.md`

### 8. Review and report

Present to the user:
- **Dataset coverage map** — existing datasets + the planned new one, showing which scenarios are covered where
- The gap analysis (what errors, what scenarios needed, what data volume needed)
- The hypothesis (what you're testing)
- The script (what bots will say)
- The manifest (complete plan)
- **Relationship to existing datasets** — does this complement or supersede?

Ask the user to review before proceeding to collection:
- Are the scenarios right? Is the data volume sufficient?
- Is the hypothesis plausible?
- Is anything missing from the data capture plan?
- Is the infra compatible with existing datasets for combining?
- Does the infra need changes? If yes → `/env-setup` first, then `/collect`
- If infra is fine → `/collect`

Log: `EXPAND: manifest ready — dataset: {id}, scenarios: {list}, hypothesis: {description}, complements: {existing-ids}`
