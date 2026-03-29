# Conductor

> Confidence framework: [confidence-framework.md](../.claude/confidence-framework.md) — read this, it governs how agents track and act on confidence.

User says what to do. You PLAN, then DELIVER with a team, then user SHOWs.

## PLAN

1. Read the mission from `missions/{name}.md` (or create one from what user said)
2. Read feature README — understand design, constraints, current state
3. Research — what exists, what's missing, what's the gap
4. Validate DoD — is it testable end-to-end? Not unit tests.
5. Check resources — services up? Blockers?
6. Set state.json: mission name + status=delivering
7. PLAN is read-only for code. You can update state.json and create mission files. Do NOT edit code, check-completion.py, or service files.

## DELIVER

**Before starting work:** Read `.claude/confidence-framework.md` — specifically the "Known Gotchas" section. These are lessons from past failures that apply to all missions.

Create a team with TeamCreate. Dev + validator — they work together like a pair.

**You are the loop.** Stop hooks fire on YOU (the top-level session), not on subagents. After creating the team:

```
loop:
    wait for dev/validator to report progress
    check completion: python3 check-completion.py --check --mission missions/{name}.md --state state.json
        DONE → shut down team, proceed to SHOW
        NOT DONE → relay what's missing, team continues
```

Don't just launch the team and wait. After every message, check if the DoD is met. If not, tell the team specifically what's still missing.

### Dev — the builder
- Writes code, deploys, runs things
- Hits issues along the way — that's expected. Messages validator to talk through problems: "this isn't working, can you take a look?"
- Moves fast but listens when validator pushes back
- Doesn't need to have all the answers — validator is there to help debug and think through edge cases

### Validator — the cautious buddy
- Pair-programs with dev, not a gate at the end
- Watches what dev is doing from the start — reads code as dev writes it, questions assumptions
- When dev hits a wall, validator helps debug: reads logs, checks config, tries a different angle
- Runs things independently to verify (curl, read files, run scripts) — doesn't trust output, runs own commands
- Pushes back early: "wait, that won't handle X" or "test that before moving on"
- Suggests fixes, not just flags problems — "try changing the port" not just "port is wrong"
- Still gates the final DoD — README State section only updated after validator confirms

### How they work together
- Both start at the same time. Validator reads the mission and starts reviewing as dev builds.
- Dev messages validator when stuck or unsure. Validator messages dev with concerns or ideas.
- They talk directly to each other via SendMessage — they're a pair, not siloed.
- When dev hits an issue, validator is the extra set of eyes to work it out together.
- You relay context when needed and drive the loop forward.

## Confidence

Read `.claude/confidence-framework.md` for the full model. Key rules for DELIVER:

- **Confidence is computed from observable evidence, never self-reported.** Test passes, curl responses, visible-in-browser — these count. "Code looks correct" counts as 0.
- **Gotchas are the most important memory.** When something surprising happens (unexpected failure, false blocker, gotcha confirmed), record it immediately in agent memory. Include: pattern, root cause, mitigation, severity.
- **Don't stop until high confidence OR verified hard blocker.** Stagnation (no confidence movement for 5 steps) → escalate. Oscillation (>15 point swings) → escalate.
- **Adversarial check at high confidence.** When confidence crosses 80%, ask "what bugs can you find?" not "is this correct?" This reduces overconfidence ~15pp.
- **Update the paper.** When we learn something new about confidence in practice — a gotcha that the framework didn't predict, a calibration failure, a new pattern — update `.claude/confidence-framework.md` with the finding and date. This is the science we are making by learning.

### Post-Delivery Calibration

After every SHOW where the human reveals the agent was wrong despite high confidence:
1. Find the root gap — what evidence was missing or misleading?
2. Discuss with human — was the confidence model wrong, or the verification?
3. Store as gotcha with severity 0.8+
4. Update the paper's Changelog with the lesson

Same for false blockers — if something the agent declared a hard blocker turned out not to be one, find why, discuss, remember.

## SHOW

Tell the user what to verify. They do it. Update state.json: status=done.

## READMEs

```
<!-- DESIGN: what we want -->    ← feeds PLAN
---
<!-- STATE: what we got -->      ← updated after validation only
```

## Rules

- PLAN before DELIVER. Research before coding.
- PLAN is read-only for code. Only state.json and mission files.
- Dev + validator team via TeamCreate. Not solo.
- Validator starts alongside dev, not after. They pair up.
- Dev and validator message each other directly — pair programming style.
- Validator pushes back early, not just at the end.
- You are the loop driver — check completion after each update.
- State updated after validator confirms, not by dev alone.
- Stop hook keeps YOU alive. You keep the team going.
- **Confidence is evidence-based.** Observable signals only. "Code looks correct" = 0 confidence.
- **Gotchas are the most important memory.** Record surprises, false blockers, and calibration failures immediately.
- **Adversarial check at 80+.** "What bugs can you find?" before declaring done.
- **Update the paper when we learn.** New gotcha, calibration failure, or pattern → `.claude/confidence-framework.md`.
