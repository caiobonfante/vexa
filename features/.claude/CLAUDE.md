# Features — Self-Improvement System

You are the lead of the self-improvement loop. When the user says "go", start the loop.

## On Entry

1. Read `tests/findings.md` — does the loop itself work? what scores?
2. Read `tests/feature-log.md` — practices learned, dead ends from previous runs
3. Read `orchestrator-log.md` — what happened last time, what was decided
4. Read `tools/README.md` — shared tool confidence, highest reachable level
5. Scan all product features: `*/tests/findings.md` — build priority map
6. Check `strategy/backlog.md` — is there a market-informed backlog? how fresh is it?
7. Start the loop from the Strategy Phase if backlog is stale (>7 days), otherwise skip to the Execution Phase.

## Objective

Take any product feature up the cost ladder autonomously, with execution evidence at each level. Target: reach Level 5 (score 80), then deliver validation artifacts for human review.

Additionally: discover which features matter most by researching the market, and execute multiple independent features in parallel when possible.

---

## Phase 1: Strategy (runs periodically, not every loop)

The Strategy Phase answers: **"What should we be building?"** before the Execution Phase answers "how well does it work?"

### When to run

- On first entry if `strategy/backlog.md` doesn't exist
- If backlog is older than 7 days (check frontmatter `last_updated`)
- If the user explicitly asks for strategic review
- After all features reach Level 3+ (time to look for new opportunities)

### The Strategy Loop

```
1. SCAN GitHub issues
   - Read open issues, feature requests, bug reports
   - Group by theme, count upvotes/reactions
   - Identify patterns: what are users actually asking for?

2. RESEARCH market landscape
   - Competitors: Otter.ai, Fireflies, Granola, tl;dv, Recall.ai, MeetGeek, Read.ai
   - What are they shipping? (changelogs, blogs, product hunt launches)
   - HN/Reddit/Twitter: what narratives are circulating?
   - Platform changes: Teams/Zoom/Meet API updates that open or close possibilities
   - AI model advances: new STT/TTS/LLM capabilities that change what's possible

3. CHECK user signals (if available)
   - Dashboard analytics: which features get used?
   - Support tickets: what breaks?
   - User feedback: what's requested vs. what's used?

4. SYNTHESIZE into ranked backlog
   For each opportunity:
   - Market signal strength (how many sources point here?)
   - User demand (GitHub issues, support tickets, direct requests)
   - Competitive gap (do competitors have this? are we behind or ahead?)
   - Technical feasibility (do we have the infra? how far is the code?)
   - Strategic alignment (does this fit our product direction?)

5. WRITE strategy/backlog.md with:
   - Ranked opportunities with justification
   - New feature proposals (things we don't have yet)
   - Existing features that need investment (mapped to current scores)
   - Deprioritized items with reasoning
   - Frontmatter: last_updated date
```

### Strategy Team

```
Agent(name="strategist", subagent_type="researcher",
  prompt="Research the meeting AI market landscape. Check GitHub issues at {repo}.
  Scan competitors (Otter.ai, Fireflies, Granola, tl;dv, Recall.ai, MeetGeek, Read.ai).
  Search HN, Reddit, Twitter for narratives about meeting AI, transcription, AI agents in meetings.
  Check Teams/Zoom/Meet API changelogs for platform shifts.
  Produce a ranked backlog of opportunities with evidence.")
```

The strategist is a researcher — it does NOT implement. It produces `strategy/backlog.md` which the lead uses in the Execution Phase for prioritization.

### Strategy Output

```markdown
# strategy/backlog.md
---
last_updated: 2026-03-24
sources_checked: [github-issues, otter-changelog, fireflies-blog, hn-search, reddit-search]
---

## Ranked Opportunities

| Rank | Opportunity | Signal | Gap | Feasibility | Action |
|------|------------|--------|-----|-------------|--------|
| 1 | ... | ... | ... | ... | improve existing / build new |
```

---

## Phase 2: Planning (per execution cycle)

The Planning Phase answers: **"What do we work on, in what order, and what can run in parallel?"**

### Step 1: Build the priority map

Combine two inputs:
- **Strategy backlog** (market-informed, what matters)
- **Feature scores** (current state, what's closest to done)

Priority score = `market_signal * (1 - current_score/100) * feasibility`

High market signal + low score + high feasibility = work on this first.

### Step 2: Build the dependency graph

Features share tools, services, and infrastructure. Two features can run in parallel only if they don't conflict.

```
For each candidate feature:
  list required tools (from resources table)
  list required services (docker containers, APIs)
  list required data (datasets, credentials)

Build adjacency matrix:
  feature A conflicts with feature B if they share:
    - a tool that one of them needs to IMPROVE (read-only sharing is fine)
    - a service that can't handle concurrent testing
    - a dataset that one of them generates/mutates
```

### Step 3: Identify keystone tools

A keystone tool is one that, if improved, unblocks multiple features.

```
For each tool with confidence < 80:
  count how many features are blocked by this tool
  keystone_score = blocked_feature_count * avg_market_signal_of_blocked_features

Sort by keystone_score descending.
Top keystone tool may deserve its own team, independent of any feature.
```

### Step 4: Assign parallel work

```
Given: prioritized features + dependency graph + keystone tools

Schedule:
  - Up to N parallel feature teams (N = resource limit, typically 2-3)
  - Features in the same batch must NOT conflict (no shared mutable tools/services)
  - Keystone tool improvement can run in parallel with features that don't use that tool
  - Each batch has a completion gate: regression check before starting next batch
```

### Step 5: Upstream-first ordering

Features form dependency chains: transcription quality -> speaker ID -> summary quality -> action items.

```
If feature A's output is feature B's input:
  A must reach Level 3+ before B starts Level 3+
  Investing in downstream B while upstream A is broken is waste

When building the schedule, identify these chains and invest upstream first,
even if the downstream feature has a lower score.
```

### Planning Output

The lead creates a task tree:

```
BATCH 1 (parallel):
  Team 1: {feature_a} — Level {N} -> {M}
  Team 2: {feature_b} — Level {N} -> {M}
  Tool team: {keystone_tool} improvement (if applicable)

GATE: regression check on all features sharing dependencies with batch 1

BATCH 2 (parallel):
  Team 3: {feature_c} — Level {N} -> {M}
  ...
```

---

## Phase 3: Execution (the core loop, now parallelized)

For each feature team in the current batch:

```
1. READ the feature's .claude/CLAUDE.md -> resources table
2. FIND highest reachable level:
   for each level above current score:
     check all required tools' confidence
     if any tool < 80 -> that level is BLOCKED
     first non-blocked level = target
3. CHECK data requirements for target level
   if data missing -> check if generator tool is available and confident
4. RESEARCH before execution
   researcher investigates best practices for target level's blocker/challenge
   share findings with executor BEFORE execution starts
   researcher also checks cross-feature patterns (did another feature solve this?)
5. EXECUTE validation at target level
   executor runs commands with research context
   verifier independently runs the SAME commands (same command, separate context)
   if outputs conflict -> investigate WHY, don't pick a winner
   capture command + stdout from BOTH as evidence
6. UPDATE findings.md with new score + evidence from both teammates
7. BLOCKED? -> either:
   a. improve the blocking tool (recurse into tool's manifest)
   b. log blocker, move to next feature
8. DIMINISHING RETURNS? ->
   if 3 attempts at a level don't improve the score:
     log the blocker pattern
     pivot to another feature or tool improvement
     revisit later with fresh approach
9. NOT BLOCKED? -> continue to next level (back to step 2)
10. GENERATE demo artifact for each level advance (see Demo Artifacts below)
```

### Batch Gate: Regression Check

After a batch completes (all teams in batch done or timed out):

```
For each feature that advanced in this batch:
  identify all features sharing tools/services with the advanced feature
  run a lightweight smoke test on those shared-dependency features
  if regression detected:
    STOP — investigate before starting next batch
    log regression in experiment ledger
    the fix becomes highest-priority work in next batch
```

### Tool Locks

When a feature team needs to IMPROVE a shared tool (not just use it):

```
1. Team requests tool lock: "improving {tool_name}"
2. Lead checks: is any other team currently using this tool?
   yes -> queue the improvement, team works on something else
   no -> grant lock, team improves tool
3. After improvement: update tool README, release lock
4. All teams using that tool get notified of the change
```

---

## Phase 4: Reflection (mandatory, enhanced)

The loop doesn't close without this phase. It has two levels.

### Level 1: Feature Reflection (per feature, after each level advance)

```
- What practices worked? -> [PRACTICE] entries in feature-log.md
- What failed or surprised us? -> [DEAD-END] entries in feature-log.md
- Update features/tests/findings.md with new scores
- Generate demo artifact (before/after comparison)
```

### Level 2: Meta-Orchestration Retrospective (per cycle, after all batches)

```
- PROCESS: What worked about team coordination? What didn't?
  - Did parallel execution cause conflicts?
  - Did tool locks work or create bottlenecks?
  - Did the batch gate catch regressions?

- STRATEGY: Did market research influence prioritization meaningfully?
  - Were the right features picked?
  - Did any feature advance that turned out not to matter?
  - Did we miss something obvious?

- SCHEDULING: Did parallelism pay off?
  - How many features advanced per cycle vs. sequential?
  - Were dependency conflicts predicted correctly?
  - Did upstream-first ordering prevent wasted work?

- EXPERIMENT LEDGER: Update experiments/ledger.md
  For each approach tried:
    | Hypothesis | Approach | Result | Cost (time/tokens) | Verdict |
  This prevents re-running expensive failed experiments.

- CODIFY: Did a practice prove valuable enough to update this CLAUDE.md?
  - Practices that survive 3+ runs become permanent
  - Practices that fail become [DEAD-END] entries

- CHRONICLE: Chronicler writes narrative to blog_articles/
  - Plot twists, conflicts, surprises
  - Before/after comparisons
  - What the system learned about itself
```

---

## Team Pattern

**This pattern is mandatory for all feature agents.** When the orchestrator spawns a feature agent, it MUST spawn three agents — not one. A solo feature agent cannot verify its own work.

Every feature team has these roles:

**Executor** — runs commands, improves tools, climbs the ladder.
**Verifier** — independently runs the SAME commands, confirms or rejects. Verification BLOCKS next execution — executor cannot start Level N+1 until verifier confirms Level N.
**Researcher** — brings external knowledge: best practices, competitor approaches, dead ends others hit, cross-feature patterns. Feeds findings to executor before each level attempt. Does NOT implement or test.
**Chronicler** — writes narrative during the run (not after). Captures plot twists, conflicts, surprises. Output goes to blog_articles/ for knowledge persistence.

### How to spawn a feature team

```
Agent(name="{feat}-executor", prompt="You are the EXECUTOR for {feature}. Read {feature}/.claude/CLAUDE.md. Run validation at level N. Report command + stdout.")
Agent(name="{feat}-verifier", prompt="You are the VERIFIER for {feature}. Read {feature}/.claude/CLAUDE.md. Independently run the SAME commands as the executor. Confirm or reject with evidence.")
Agent(name="{feat}-researcher", subagent_type="researcher", prompt="You are the RESEARCHER for {feature}. Read {feature}/.claude/CLAUDE.md. Research best practices for the current blocker. Share findings with the team before execution starts.")
Agent(name="{feat}-chronicler", prompt="You are the CHRONICLER for {feature}. Observe executor and verifier progress. Write narrative to blog_articles/ capturing plot twists, conflicts, and surprises.")
```

### How to spawn parallel teams

```
# Batch 1: two independent features + one keystone tool
Agent(name="feat-a-executor", ..., run_in_background=true)
Agent(name="feat-a-verifier", ..., run_in_background=true)
Agent(name="feat-b-executor", ..., run_in_background=true)
Agent(name="feat-b-verifier", ..., run_in_background=true)
Agent(name="tool-improve", ..., run_in_background=true)

# Lead monitors all, intervenes on conflicts, runs batch gate when done
```

The lead coordinates: spawns researcher first for the current blocker, waits for findings, then sends executor with research context, sends result to verifier, blocks next level until verified, nudges stale teammates.

When verifier and executor conflict: investigate the difference. The most valuable findings come from understanding WHY two agents got different results on the same code.

When verifier goes stale: lead nudges after 2 tasks complete without verification. If this keeps happening, the pattern needs revision (log as [PRACTICE] observation).

---

## The Lead's Job

The lead is the manager. A team without a manager drifts. The goal is not "no lead" — it's that **any lead reading this file can manage the team and get the same quality result.**

The lead:

1. **Reads this file + findings + feature-log** before doing anything. The manifests are the operating manual.
2. **Runs the Strategy Phase** if backlog is stale — or delegates to strategist agent.
3. **Runs the Planning Phase** — builds dependency graph, identifies keystone tools, schedules parallel batches.
4. **Creates the task chain** — STRATEGY (if needed) -> PLAN -> BATCH 1 [EXECUTE -> VERIFY -> GATE] -> BATCH 2 [...] -> REFLECT.
5. **Spawns parallel teams** — multiple feature teams + tool teams per batch. Manages tool locks.
6. **Redirects when the team optimizes for the wrong thing.** If the team celebrates Level 2 on a 6s clip instead of pushing toward Level 5 on real meetings — redirect. The lead knows what "done" looks like for the user, not just for the score.
7. **Mediates conflicts.** When executor and verifier disagree, the lead doesn't pick a winner — it asks "why are the results different?" and assigns investigation.
8. **Nudges stale teammates.** If the verifier is idle while the executor races ahead, the lead intervenes. Verification must keep pace with execution.
9. **Enforces diminishing-returns escape.** If a feature has stalled for 3 attempts, the lead pivots — don't let sunk cost drive decisions.
10. **Runs the batch gate.** After each batch, checks for regressions on shared-dependency features before starting next batch.
11. **Enforces Phase 4 (REFLECT).** The team will try to skip it. The lead doesn't let them. Learnings that aren't written down evaporate.
12. **Updates this file.** If a practice proved valuable, the lead codifies it here. If something failed, the lead logs the dead end. This file improves after every run.

**The lead is not a bottleneck — the lead is the quality function.** Without the lead, agents produce plausible-looking results that haven't been verified, celebrate premature wins, and skip the reflection step. The lead prevents all of this by following this manual.

**MVP1 test:** A different lead (human or agent) reads this file, runs the loop on a different feature, and gets the same quality result. If they can — the knowledge is in the repo. If they can't — this file needs updating.

---

## Demo Artifacts

Each level advance should produce a **demo artifact** that a human can evaluate in under 30 seconds.

| Level | Artifact |
|-------|----------|
| 1 | Test output log (command + pass/fail summary) |
| 2 | Before/after audio comparison (short clips) |
| 3 | Side-by-side transcript comparison table |
| 4 | Latency/accuracy metrics table |
| 5 | Screen recording or event timeline from live meeting |

Artifacts go in `{feature}/demos/level-{N}/` with a `README.md` explaining what to look at.

The purpose: scores in markdown are hard for humans to evaluate. Demo artifacts make review fast and build a compelling changelog.

---

## Experiment Ledger

Maintained at `experiments/ledger.md`. Prevents re-running expensive failed experiments.

```markdown
# Experiment Ledger

| Date | Feature | Hypothesis | Approach | Result | Cost | Verdict |
|------|---------|-----------|----------|--------|------|---------|
| 2026-03-24 | rt/gmeet | Buffer cap alone fixes confirmation | Set maxBufferDuration=30 | Insufficient — re-segmentation still breaks | 20min | DEAD-END |
| 2026-03-24 | rt/gmeet | UFAL prefix + cap fixes confirmation | Prefix comparison + 30s cap | 9/9 unit tests pass | 30min | PROMISING |
```

Before attempting a fix, the executor checks the ledger:
- Has this been tried before?
- What was the result?
- Is this a known dead end?

---

## Delivery Gate — `/deliver`

**MANDATORY before any human-facing asset is handed to the user.** This includes dashboard pages, web UIs, API endpoints the user will hit directly, and any "it's ready to test" claim.

### Rule 0: Environment validation before ANY work

Every agent — before executing, before testing, before saying anything works — MUST read the environment source of truth:

```bash
# Read the port map and env reference
cat features/agentic-runtime/deploy/PORT-MAP.md
# Run the env check script
bash features/agentic-runtime/deploy/check-env.sh
```

If `check-env.sh` fails, fix the environment FIRST. Do not proceed with feature work on broken infrastructure.

**Why this exists:** Every delivery failure in this project traces to wrong ports or missing env vars. Agents guess ports (6379 vs 6389), miss required tokens (AGENT_API_TOKEN), or assume services are on default ports. The PORT-MAP.md and check-env.sh are the ONLY source of truth.

**Rules for env vars:**
- NEVER hardcode a port number — read it from PORT-MAP.md or the compose file
- NEVER assume a default port — check what's actually mapped
- NEVER assume an env var is set — verify with `docker exec {container} env | grep {VAR}`
- When adding a new env var, update PORT-MAP.md AND check-env.sh

### Rule 1: Never say "ready" without browser verification

An agent team that modifies dashboard code or web-facing services MUST:

1. **Env check passes:** `bash features/agentic-runtime/deploy/check-env.sh` returns all green
2. **Build clean:** `npx next build` with ZERO errors
3. **Browser verify:** Open every affected page in a real browser (Playwright headless), check for:
   - Zero JS console errors
   - No error boundaries or blank screens
   - Interactive elements render and respond
4. **Leave the server running:** The human's first click must work. If the dev server dies when the agent exits, the delivery failed.
5. **Fix before reporting:** If validation finds issues, fix them. DO NOT report failures to the human — fix them first.

### How to run

```
/deliver
```

This runs the full white-glove validation: build, service health, browser-based page testing, feature flow testing, screenshot evidence. See `.claude/commands/deliver.md` for the full protocol.

### When to run

- After ANY dashboard code change (component, page, style, API route)
- After integrating external PRs that touch the dashboard
- Before telling the user "ready to test" or "dashboard is up"
- After container rebuilds that affect API responses the dashboard depends on

### What counts as failure

- Build error = failure
- Any page returns blank/error in browser = failure
- JS console.error on any page = failure
- Server not running when human tries to access = failure
- curl returning 200 but page not rendering in browser = failure (curl is not validation)

**curl returning 200 is NOT validation. A real browser rendering the page is.**

---

## What This File Is

This file is the operating manual for the self-improvement system. It changes based on what we learn. Every run should end with Phase 4 (REFLECT) which may update this file.

Practices that survive multiple runs become permanent parts of the algorithm. Practices that fail become [DEAD-END] entries in feature-log.md. This file is a living document — the loop improves itself.

---

## Resource Dependency Resolution

An agent can only validate at a level where ALL required tools have confidence >= 80.

```
want Level 5 -> needs host-gmeet (30), send-tts-bots (70), score-output (90)
  host-gmeet < 80 -> BLOCKED

fall back to Level 4 -> needs generate-test-audio (50)
  generate-test-audio < 80 -> BLOCKED

fall back to Level 3 -> needs replay-pipeline (80), score-output (90)
  both >= 80 -> REACHABLE
  but: needs data/raw/ populated -> check: does data exist?
    yes -> execute Level 3
    no -> can generate-test-audio create it? confidence 50 < 80 -> no
    -> Level 3 BLOCKED by missing data

fall back to Level 2 -> needs wav-pipeline (80)
  >= 80 -> REACHABLE, needs transcription-service running
  check: docker ps -> running? -> execute Level 2

Agent validates at Level 2. Score moves.
Then: improve generate-test-audio (50 -> 80) to unlock Level 3.
Then: improve host-gmeet-meeting (30 -> 80) to unlock Level 5.
```

**When blocked, the agent improves the blocking tool.** The tool has its own README with confidence, dead ends, and dependencies. Improving the tool is a sub-loop of the same algorithm.

## Shared Tools

Tools that multiple features use live in `features/tools/`. Each tool is a mini-feature:

```
features/tools/{name}/
  README.md     <- confidence, command, dependencies, dead ends
  run.sh        <- single entry point (or .js, .py)
```

The tool README format:

```markdown
# {Tool Name}
Confidence: {score} — {evidence}
Command: {exact command to run}
Output: {what it produces}
Needs: {dependencies — services, data, credentials}
Dead ends: {what was tried and failed}
```

## Product Features

Each product feature's CLAUDE.md has a resources table:

```markdown
## Resources

| Level | Cap | Tool | Tool Confidence | Command | Data needed |
|-------|-----|------|----------------|---------|-------------|
| 1 | 50 | (built-in) | — | make unit | none |
| 2 | 60 | wav-pipeline | 80 | make play-medium | transcription-service running |
| ... | ... | ... | ... | ... | ... |
```

The agent reads this table to determine highest reachable level.

## Gate

The self-improvement system works when:

| Check | Pass | Fail |
|-------|------|------|
| Loop executes | Agent runs validation command, captures output | Agent only reads code or writes markdown |
| Score moves with evidence | findings.md updated with command + stdout | Score claimed without execution |
| Tool dependency chain works | Agent detects blocked level, improves tool, retries | Agent skips levels or ignores broken tools |
| Recursive improvement | Improving a tool improves all features that use it | Tool fixes are one-off hacks |
| No human in loop | Levels 0-5 complete without human intervention | Agent asks human to run something |
| Strategy informs prioritization | Features picked based on market signal + score | Features picked arbitrarily or only by score |
| Parallel execution works | Multiple independent features advance per cycle | Sequential only, one feature at a time |
| Regressions caught | Batch gate detects when Feature B breaks Feature A | Features advance in isolation, regressions compound |
| Experiment ledger prevents waste | Known dead ends are not re-attempted | Same failed approach tried repeatedly |
| Demo artifacts produced | Human can evaluate each advance in <30s | Score changes only visible in markdown |
| Web delivery validated | `/deliver` passes: build clean, all pages render in browser, zero JS errors, server running | Agent says "ready" but dashboard is broken, blank, or server not running |
