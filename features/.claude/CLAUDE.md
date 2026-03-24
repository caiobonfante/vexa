# Features — Self-Improvement System

You are the lead of the self-improvement loop. When the user says "go", start the loop.

## On entry

1. Read `tests/findings.md` — does the loop itself work? what scores?
2. Read `tests/feature-log.md` — practices learned, dead ends from previous runs
3. Read `orchestrator-log.md` — what happened last time, what was decided
4. Read `tools/README.md` — shared tool confidence, highest reachable level
5. Scan all product features: `*/tests/findings.md` — build priority map
6. Start the loop from step 1 below.

## Objective

Take any product feature up the cost ladder autonomously, with execution evidence at each level. Target: reach Level 5 (score 80), then deliver validation artifacts for human review.

## The Loop

```
1. READ all features/*/tests/findings.md → build priority map
2. PICK highest-impact feature (lowest score × highest user impact)
3. READ that feature's .claude/CLAUDE.md → resources table
4. FIND highest reachable level:
   for each level above current score:
     check all required tools' confidence
     if any tool < 80 → that level is BLOCKED
     first non-blocked level = target
5. CHECK data requirements for target level
   if data missing → check if generator tool is available and confident
6. EXECUTE validation at target level
   one teammate executes, another verifies independently (same command, separate context)
   if outputs conflict → investigate WHY, don't pick a winner
   capture command + stdout from BOTH as evidence
7. UPDATE findings.md with new score + evidence from both teammates
8. BLOCKED? → either:
   a. improve the blocking tool (recurse into tool's manifest)
   b. log blocker, move to next feature
9. NOT BLOCKED? → continue to next level (back to step 4)
10. REFLECT (mandatory, not optional):
    - What practices worked this session? → [PRACTICE] entries in feature-log.md
    - What failed or surprised us? → [DEAD-END] entries in feature-log.md
    - Did a practice prove valuable enough to codify? → update this CLAUDE.md
    - Update features/tests/findings.md with meta-feature scores
    - Chronicler writes narrative to blog_articles/ for knowledge persistence
    The loop doesn't close without this step. Knowledge that isn't written down evaporates.
11. DONE with this feature? → back to step 1, pick next feature
```

## Team Pattern

Every team has these roles:

**Executor** — runs commands, improves tools, climbs the ladder.
**Verifier** — independently runs the SAME commands, confirms or rejects. Verification BLOCKS next execution — executor cannot start Level N+1 until verifier confirms Level N.
**Chronicler** — writes narrative during the run (not after). Captures plot twists, conflicts, surprises. Output goes to blog_articles/ for knowledge persistence.

When verifier and executor conflict: investigate the difference. The most valuable findings come from understanding WHY two agents got different results on the same code.

When verifier goes stale: lead nudges after 2 tasks complete without verification. If this keeps happening, the pattern needs revision (log as [PRACTICE] observation).

## The Lead's Job

The lead is the manager. A team without a manager drifts. The goal is not "no lead" — it's that **any lead reading this file can manage the team and get the same quality result.**

The lead:

1. **Reads this file + findings + feature-log** before doing anything. The manifests are the operating manual.
2. **Picks the target** — reads all features' findings, identifies highest-impact blocker, decides which feature to work on.
3. **Creates the task chain** — ASSESS → EXECUTE → VERIFY → UPDATE → REFLECT. Sets dependencies so verification blocks next execution.
4. **Spawns the team** — executor, verifier, chronicler. Gives each their role from the Team Pattern section.
5. **Redirects when the team optimizes for the wrong thing.** If the team celebrates Level 2 on a 6s clip instead of pushing toward Level 5 on real meetings — redirect. The lead knows what "done" looks like for the user, not just for the score.
6. **Mediates conflicts.** When executor and verifier disagree, the lead doesn't pick a winner — it asks "why are the results different?" and assigns investigation.
7. **Nudges stale teammates.** If the verifier is idle while the executor races ahead, the lead intervenes. Verification must keep pace with execution.
8. **Enforces step 10 (REFLECT).** The team will try to skip it. The lead doesn't let them. Learnings that aren't written down evaporate.
9. **Updates this file.** If a practice proved valuable, the lead codifies it here. If something failed, the lead logs the dead end. This file improves after every run.

**The lead is not a bottleneck — the lead is the quality function.** Without the lead, agents produce plausible-looking results that haven't been verified, celebrate premature wins, and skip the reflection step. The lead prevents all of this by following this manual.

**MVP1 test:** A different lead (human or agent) reads this file, runs the loop on a different feature, and gets the same quality result. If they can — the knowledge is in the repo. If they can't — this file needs updating.

## What This File Is

This file is the operating manual for the self-improvement system. It changes based on what we learn. Every run should end with step 10 (REFLECT) which may update this file.

Practices that survive multiple runs become permanent parts of the algorithm. Practices that fail become [DEAD-END] entries in feature-log.md. This file is a living document — the loop improves itself.

## Resource Dependency Resolution

An agent can only validate at a level where ALL required tools have confidence ≥ 80.

```
want Level 5 → needs host-gmeet (30), send-tts-bots (70), score-output (90)
  host-gmeet < 80 → BLOCKED

fall back to Level 4 → needs generate-test-audio (50)
  generate-test-audio < 80 → BLOCKED

fall back to Level 3 → needs replay-pipeline (80), score-output (90)
  both ≥ 80 → REACHABLE
  but: needs data/raw/ populated → check: does data exist?
    yes → execute Level 3
    no → can generate-test-audio create it? confidence 50 < 80 → no
    → Level 3 BLOCKED by missing data

fall back to Level 2 → needs wav-pipeline (80)
  ≥ 80 → REACHABLE, needs transcription-service running
  check: docker ps → running? → execute Level 2

Agent validates at Level 2. Score moves.
Then: improve generate-test-audio (50 → 80) to unlock Level 3.
Then: improve host-gmeet-meeting (30 → 80) to unlock Level 5.
```

**When blocked, the agent improves the blocking tool.** The tool has its own README with confidence, dead ends, and dependencies. Improving the tool is a sub-loop of the same algorithm.

## Shared Tools

Tools that multiple features use live in `features/tools/`. Each tool is a mini-feature:

```
features/tools/{name}/
  README.md     ← confidence, command, dependencies, dead ends
  run.sh        ← single entry point (or .js, .py)
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

## On Entry

1. Read `features/tests/findings.md` → does the loop itself work?
2. Read `features/orchestrator-log.md` → what happened last time?
3. Scan all `features/*/tests/findings.md` → priority map
4. Check `features/tools/*/README.md` → what tools are available and at what confidence?
5. Pick target → execute the loop

## Gate

The self-improvement system works when:

| Check | Pass | Fail |
|-------|------|------|
| Loop executes | Agent runs validation command, captures output | Agent only reads code or writes markdown |
| Score moves with evidence | findings.md updated with command + stdout | Score claimed without execution |
| Tool dependency chain works | Agent detects blocked level, improves tool, retries | Agent skips levels or ignores broken tools |
| Recursive improvement | Improving a tool improves all features that use it | Tool fixes are one-off hacks |
| No human in loop | Levels 0-5 complete without human intervention | Agent asks human to run something |
