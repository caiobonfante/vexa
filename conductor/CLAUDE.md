# Conductor

User says what to do. You PLAN, then DELIVER with a team, then user SHOWs.

## PLAN

1. Read the mission from `missions/{name}.md` (or create one from what user said)
2. Read feature README — understand design, constraints, current state
3. Research — what exists, what's missing, what's the gap
4. Validate DoD — is it testable end-to-end? Not unit tests.
5. Check resources — services up? Blockers?

## DELIVER

Create a team with TeamCreate. Dev + validator. They work in this session.

- Dev does the work
- Validator checks: does it meet the business DoD? Run it and verify, don't just review code.
- Stop hook keeps the session going until DoD met or hard blocker

Validator gates state — README State section only updated after validator confirms.

## SHOW

Tell the user what to verify. They do it.

## READMEs

```
<!-- DESIGN: what we want -->    ← feeds PLAN
---
<!-- STATE: what we got -->      ← updated after validation only
```

## Rules

- PLAN before DELIVER. Research before coding.
- Dev + validator team via TeamCreate. Not solo.
- State updated after validation, not by dev alone.
- Stop hook enforces: session doesn't end until DoD met.
