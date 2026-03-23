# /collect — Run a collection run to produce a tagged dataset

You are in **Stage 1: COLLECTION RUN**. Your job is to capture real-world behavior into a properly tagged **dataset** that the sandbox can replay. You are gathering data, not improving the pipeline. Collection runs are expensive — get everything in one shot.

Read the full stage protocol: `features/README.md` (section: Stage 1: COLLECTION RUN)
Read dataset structure: `features/README.md` (section: Datasets)
Read the glossary: `features/README.md` (section: Glossary)

## Your constraints

- Do NOT change pipeline code — you're capturing a baseline, not iterating
- Do NOT discard partial or "bad" data — it may reveal real platform behavior
- Do NOT run multiple scripts in one session unless scenarios are independent
- Do NOT assume capture is working — verify before running the full script
- Do NOT start without a collection manifest
- Do NOT save data outside the dataset directory — one collection run = one dataset

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

### 4. Create the dataset directory

Generate the **dataset ID**: `{platform}-{N}sp-{scenario-tag}-{YYYYMMDD}`

```
data/raw/{id}/
  manifest.md          # Copy from collection manifest, will be completed during collection
  ground-truth.txt     # Will be filled during collection
  infra-snapshot.md    # Copy from current infra snapshot
  audio/               # WAV files
  events/              # Platform events
  pipeline/            # Pipeline output
  README.md            # Human summary (written after collection)
```

Copy the collection manifest into `manifest.md`. Copy the current infra snapshot.

## Collection procedure

### 5. Pre-run verification

Before running the full script:
1. Set up the meeting environment (platform, meeting link)
2. Send ONE test utterance through the pipeline
3. Verify ALL data types from the manifest's capture checklist are being logged:
   - Audio being recorded? Check WAV output.
   - Caption events being captured? Check log output.
   - Pipeline output being logged? Check bot logs.
   - Timestamps present and synchronized? Compare across data sources.
4. If any data type is missing, fix the capture before proceeding

### 6. Run the collection

1. Start all bots — they join the meeting
2. Bots speak from the script at the specified timing
3. Monitor capture in real-time — watch for gaps, errors, disconnections
4. When script completes, wait for pipeline to finish processing (idle timeout + buffer flush)
5. Stop capture

### 7. Save data into the dataset

Save all files into the dataset directory:

| Destination | What goes here |
|-------------|---------------|
| `ground-truth.txt` | Script send times: `[GT] timestamp speaker "text"` |
| `audio/` | Per-utterance WAVs + combined WAV |
| `events/` | Caption events JSON, speaker change events, DOM events |
| `pipeline/` | Bot logs, draft/confirmed segments, raw logs |
| `infra-snapshot.md` | Already copied — verify it matches what was running |

### 8. Tag the dataset

Complete the dataset `manifest.md`:

1. **Fill the files table** — every file in the dataset must be listed with:
   - File path (relative to dataset root)
   - Type (ground truth / audio / collected data / pipeline output)
   - Record count (utterances, events, segments)
   - **Scenario tags** — which scenarios this file covers

2. **Tag scenarios** — verify every scenario from the manifest has at least one file covering it. If a scenario has no data → the collection is incomplete.

3. **Record baseline scoring** — run one replay, record the score in the manifest.

4. **Set status** to `active`.

5. **Write the README** — human summary:
   - What's in this dataset and why it was collected
   - Which scenarios it covers (with tags)
   - How to replay it: `make play-replay DATASET={id}`
   - What the baseline scoring was
   - Compatibility notes for combining with other datasets

### 9. Verify completeness

Walk through the manifest's scenario table:

| Scenario | Has ground truth? | Has audio? | Has events? | Has pipeline output? |
|----------|------------------|-----------|-------------|---------------------|

If any cell is empty → the dataset is incomplete. Decide: re-run or supplement.

### 10. Check against existing datasets

Read manifests of existing datasets in `data/raw/`:
- Does the new dataset supersede any existing one? (Same scenarios, better data)
- If yes, mark the old dataset as `superseded by {new-id}` in its manifest
- Does the new dataset complement existing ones? (Different scenarios)
- Document compatibility in the README (can they be combined? infra snapshots match?)

### 11. Report

Tell the user:
- **Dataset ID** and location
- **Scenarios** covered (with tags)
- **Files** collected (counts, sizes)
- **Baseline scoring** result
- **Compatibility** with existing datasets
- Ready for SANDBOX ITERATION (`/iterate`)

Update `features/{name}/tests/findings.md` with the baseline.

Log: `STAGE: collection-run complete — dataset: {id}, {N} utterances, {M} events, {K} files, baseline scoring: {X}%`
