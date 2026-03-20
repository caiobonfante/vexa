# /collect — Run a collection run to capture real-world data

You are in **Stage 1: COLLECTION RUN**. Your job is to capture real-world behavior that the sandbox can replay. You are gathering data, not improving the pipeline. Collection runs are expensive — get everything in one shot.

Read the full stage protocol: `features/README.md` (section: Stage 1: COLLECTION RUN)
Read the glossary: `features/README.md` (section: Glossary)

## Your constraints

- Do NOT change pipeline code — you're capturing a baseline, not iterating
- Do NOT discard partial or "bad" data — it may reveal real platform behavior
- Do NOT run multiple scripts in one session unless scenarios are independent
- Do NOT assume capture is working — verify before running the full script
- Do NOT start without a collection manifest

## Pre-flight checks

### 1. Verify env setup is complete

Read `features/{name}/tests/infra-snapshot.md`:
- Does it exist? If not → tell user to run `/env-setup` first
- Is it recent? If older than the last code change, flag it
- Do the services listed match what's needed?

Quick-verify: run `make env-check` from `features/{name}/tests/`

### 2. Find or create the collection manifest

Look for a collection manifest in `features/{name}/tests/`:
- Files named `collection-manifest*.md` or similar
- If coming from EXPAND, it should already exist

**If no manifest exists** (first collection run for this feature):
- Read the feature's CLAUDE.md to understand what scenarios matter
- Read existing findings if any (`features/{name}/tests/findings.md`)
- Help the user design one using the template from `features/README.md`
- The manifest MUST have: hypothesis, script, scenarios, infra requirements, data to capture, capture checklist, replay readiness

**If manifest exists:**
- Read it fully
- Verify the `.env` matches the manifest's infra requirements table
- Flag any mismatches — these must be resolved before collecting

### 3. Verify the script

The **script** in the manifest defines what bots will say. Check:
- Every utterance has a speaker, text, and timing
- Every scenario is labeled
- Timing makes sense (no impossible overlaps unless that's the scenario)
- Control scenarios from previous scripts are included (if this isn't the first run)

## Collection procedure

### 4. Pre-run verification

Before running the full script:
1. Set up the meeting environment (platform, meeting link)
2. Send ONE test utterance through the pipeline
3. Verify ALL data types from the manifest's capture checklist are being logged:
   - Audio being recorded? Check WAV output.
   - Caption events being captured? Check log output.
   - Pipeline output being logged? Check bot logs.
   - Timestamps present and synchronized? Compare across data sources.
4. If any data type is missing, fix the capture before proceeding

### 5. Run the collection

1. Start all bots — they join the meeting
2. Bots speak from the script at the specified timing
3. Monitor capture in real-time — watch for gaps, errors, disconnections
4. When script completes, wait for pipeline to finish processing (idle timeout + buffer flush)
5. Stop capture

### 6. Save data

For each data type in the manifest's capture checklist:
1. Save the file to `features/{name}/tests/` with a descriptive name
2. Verify the file is non-empty and has the expected format
3. Verify timestamps are present and cover the full script duration

Save the script as **ground truth**:
- Format: `[timestamp] [speaker] "text"` per utterance
- Use Unix timestamps from actual TTS send times (not planned times)

### 7. Verify completeness

Walk through the manifest's data table row by row:

| Data type | File exists? | Format correct? | Covers all scenarios? |
|-----------|-------------|----------------|----------------------|

If any row fails → the collection run is incomplete. Decide: re-run or supplement.

### 8. Smoke replay

Feed the collected data through the pipeline once:
- `make play-replay` or equivalent
- Does it run without errors?
- Does scoring produce a number?
- This number is the **baseline** — record it

### 9. Report

Tell the user:
- What data was collected (files, sizes, event counts)
- Baseline scoring result
- Any issues or gaps
- Ready for SANDBOX ITERATION (`/iterate`)

Update `features/{name}/tests/findings.md` with the baseline.

Log: `STAGE: collection-run complete — {N} utterances, {M} events, {K} data files, baseline scoring: {X}%`
