# /hygiene — Validate feature docs are coherent, connected, and code-aligned

You are running a documentation health check on a feature. Your job is to find every lie, broken link, stale reference, and structural gap in the feature's markdown files — then fix them or flag them.

## Constraints

- You may ONLY modify markdown files (`.md`). You must NOT touch code, config, Makefiles, or any non-markdown file.
- You read code to verify claims — you never change it. Code is ground truth; docs conform to code, not the other way around.
- You operate on the feature tree rooted at your working directory. Do not modify files outside the feature tree.

## Usage

Run from any feature directory (or subdirectory). Takes no arguments — discovers the feature from the working directory.

## Startup: identify the feature

1. Walk up from the current directory until you find a `README.md` with a `## Why` section — that's the feature root.
2. If the feature root has subdirectories with their own `README.md` files (platforms, delivery, tests), those are in scope too.
3. Read the feature's `README.md` and `.claude/CLAUDE.md` first — they're the source of truth for what to validate.

Log: `HYGIENE: feature root — {path}`

## Phase 1: Structure check

Every feature README must follow the Why / What / How pattern (see `features/README.md`).

For the **root README**, check:

| Section | Required | What it must contain |
|---------|----------|---------------------|
| `## Why` | yes | One paragraph: what job this feature does and why it matters |
| `## What` | yes | Architecture, components, data flow — the design |
| `## How` | yes | Implementation status, verification steps, config |

For **sub-READMEs** (platforms, delivery, tests): structure can vary, but each must have a clear purpose stated in its first paragraph.

**Verdict per file:** PASS (has structure) or FAIL (missing sections, empty sections, section exists but says nothing useful).

## Phase 2: Connection check

Scan all markdown files in the feature tree for links: `[text](path)`, `[text](path#anchor)`.

For each link:

1. **Internal file links** (`../something/README.md`, `./tests/findings.md`): verify the target file exists on disk.
2. **Anchor links** (`#section-name`): verify the target heading exists in the target file.
3. **Code file references** (paths like `services/vexa-bot/core/src/services/speaker-streams.ts`): verify the file exists. Search from repo root.
4. **Cross-feature links** (links to other features' READMEs): verify they exist and the referenced section exists.

Also check the reverse — are there sibling/child READMEs that the root README does NOT link to? Every README in the feature tree should be reachable from the root.

**Verdict per link:** VALID or BROKEN (with what's wrong).

## Phase 3: Code alignment

This is the most important check. Scan the README and CLAUDE.md for claims about the codebase:

### 3a. File paths and line references
Every file path mentioned (e.g., `services/vexa-bot/core/src/services/speaker-streams.ts`) — verify it exists. If a line number is mentioned, verify the content at that line matches the claim.

### 3b. Component tables
If the README has a components table with "Key file" or similar columns, verify each file exists and contains the described functionality. Grep for the class/function name if mentioned.

### 3c. Config values
If the README documents config values (parameters, thresholds, env vars), spot-check against actual code:
- Are the values still accurate?
- Are the variable names still correct?
- Does `.env.example` match what the README says?

### 3d. Data flow claims
If the README describes a data flow (A -> B -> C), verify each step:
- Does the source component exist?
- Does it actually call/emit to the next component?
- Are the data formats described accurately?

### 3e. Architecture diagrams
ASCII diagrams and mermaid charts — do the component names match actual code? Are the relationships still accurate?

**Verdict per claim:** ACCURATE, STALE (was true, no longer), or WRONG (never true or fundamentally changed).

## Phase 4: Data awareness

A feature should know its data. The data model is defined in `features/README.md` (section: data/ — Feature data organized by pipeline stage).

### 4a. Data stage declaration
Does the README have a **Data stages** table? Every feature must declare its stages:

```markdown
### Data stages
| Stage | Contents | Produced by | Consumed by |
```

Check: does the table exist? Are the stages specific (not vague)? Does it name concrete data types?

### 4b. data/ directory matches declaration
If the feature has a `data/` directory:
- Do the stage subdirectories (`raw/`, `core/`, `rendered/`) match the declared stages?
- Are there stage directories that aren't declared, or declarations without directories?
- Does every dataset directory have a `manifest.md`?
- Are there data files floating outside the stage structure (loose JSONs, WAVs in wrong places)?

### 4c. Dataset lineage
For datasets that appear in multiple stages (same ID in `raw/` and `core/`):
- Is the lineage clear? Can you trace `rendered/{id}` back to `core/{id}` back to `raw/{id}`?
- Does the README or manifest document this flow?

### 4d. Cross-feature data flow
If one feature's output is another's input (e.g., delivery consumes realtime-transcription's core output):
- Is this relationship documented in both READMEs?
- Do the paths match? (delivery references `../data/core/` and that directory exists)

### 4e. No orphan data files
Scan for data files (`.json`, `.wav`, `.txt`, `.csv`) outside `data/`:
- Are there data files in `tests/`, `delivery/`, or the feature root that should be in `data/`?
- Flag any data file not inside a `data/{stage}/{dataset-id}/` structure.

**Verdict:** AWARE (stages declared, data/ matches, lineage clear) or VAGUE (missing declarations, orphan data, broken lineage).

## Phase 5: Markdown hygiene

List every `.md` file in the feature tree. For each:

| File | Purpose | Stale? | Orphan? |
|------|---------|--------|---------|
| {path} | {what it's for} | yes/no | yes/no |

**Stale** = content references things that no longer exist (old commits, removed files, superseded approaches).
**Orphan** = not linked from any other markdown file in the feature tree AND not a well-known file (`README.md`, `CLAUDE.md`, `findings.md`, `feature-log.md`).

Flag files that should be deleted or merged.

## Phase 6: CLAUDE.md / README consistency

Compare the feature's `.claude/CLAUDE.md` against its `README.md`:

- **Scope**: does CLAUDE.md's scope match what README describes?
- **Components/edges**: are the same components listed? Any in one but not the other?
- **Certainty table**: do the checks in CLAUDE.md map to verifiable claims in the README?
- **Gate**: does the gate description match the README's verification steps?

**Verdict:** CONSISTENT or DIVERGED (with specifics).

## Phase 7: Render report

Output a single report:

```
HYGIENE REPORT: {feature-name}
Feature root: {path}
Files scanned: {count}

STRUCTURE
  {file}: PASS/FAIL — {detail}

CONNECTIONS
  Valid: {count}
  Broken: {count}
  {each broken link with file:line and what's wrong}
  Unreachable READMEs: {list of READMEs not linked from root}

CODE ALIGNMENT
  Accurate: {count}
  Stale: {count} — {each with what changed}
  Wrong: {count} — {each with what's actually true}

DATA AWARENESS: AWARE/VAGUE
  {detail}

MARKDOWN HYGIENE
  {count} files, {stale} stale, {orphan} orphan
  {each flagged file with recommendation}

CLAUDE.md CONSISTENCY: CONSISTENT/DIVERGED
  {detail}

SUMMARY: {X} issues found
  {prioritized list of fixes}
```

## Phase 8: Fix or flag

For each issue found:

- **Broken links**: fix if the target moved (update the path). Flag if the target was deleted (needs human decision).
- **Stale code references**: update to current file paths/line numbers/values if straightforward. Flag if the architecture changed.
- **Missing structure**: do NOT generate content — flag it. Only the feature owner knows the Why.
- **Orphan files**: flag for review, do NOT delete.
- **Consistency issues**: flag — let the human decide which source is authoritative.

After fixes, re-run the broken checks to verify they pass.

```
FIXES APPLIED: {count}
  {each fix: file, what changed, why}

FLAGGED FOR HUMAN: {count}
  {each flag: file, issue, why you can't auto-fix}
```

End with:

```
HYGIENE COMPLETE: {feature} — {issues} issues, {fixed} fixed, {flagged} flagged
```
