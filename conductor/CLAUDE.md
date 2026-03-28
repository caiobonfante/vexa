# Conductor

## PLAN

Team: conductor + researcher + validator. One pass, not a loop.

1. **Business DoD** — ask the user: what does "done" look like? Something they can verify by using the system end-to-end. Not unit tests — the real thing working.

2. **Researcher** investigates: read the code, check what exists, what's missing, what's the gap between Design README (what we want) and State (what we got).

3. **Validator** checks the DoD: is it testable? Is it specific enough? Can the delivery team verify it against the running system? If not, sharpen it.

4. **Check resources** — are services up? Env set? Hard blockers? If something critical is down, it's a blocker — report and stop.

5. **Build prompt file** — mission + feature README + service READMEs → `batches/{name}-prompt.txt`

6. **Give the user the command:**
```bash
CONDUCTOR_MISSION={name} claude --worktree {name} \
    --append-system-prompt-file conductor/batches/{name}-prompt.txt
```

## DELIVER

User runs the command. One terminal. Interactive. Persistent loop (Stop hook).

Inside: dev vs validator team.
- **Dev** does the work — code, deploy, test
- **Validator** checks against business DoD — not code quality, not scores. "Does the thing actually work?" Run it. Verify against the running system. If dev says "fixed" but it doesn't work, reject.

The loop: dev works → validator checks DoD → not met → dev continues. Stop hook enforces. Session doesn't end until business DoD passes or hard blocker.

**Validator gates state.** Dev produces output. Validator confirms it meets DoD. Only then does README State section update. Dev doesn't write its own scores.

## SHOW

User does the thing. Opens the dashboard. Sends the Telegram message. Joins the meeting. Either it works or it doesn't.

## READMEs

Source of truth. Every feature/service README has:

```
<!-- DESIGN: what we want — feeds into PLAN -->
Why, Data Flow, Code Ownership, Constraints
    ↑ requirements, metrics, constraints, system design

---

<!-- STATE: what we got — updated after validation only -->
Quality Bar, Certainty, Known Issues
    ↑ only updated when validator confirms output meets DoD
```

Design is the spec — where it's going.
State is honest — what it is right now.

## Rules

- Business DoD from the user, in their words
- PLAN identifies DoD + blockers + resources. Researcher + validator help.
- DELIVER is a persistent loop. Dev vs validator. Validator checks real DoD.
- State only updated after validation, never by dev alone
- SHOW is the user doing the thing
- READMEs are source of truth for where it's going (Design) and what it is (State)
