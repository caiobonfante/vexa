# Conductor

One session does everything. User launches it, it PLANs, DELIVERs, and the user SHOWs.

## PLAN (first thing you do)

1. **Business DoD** — ask the user: what does "done" look like? Something they can verify by using the system end-to-end. Not unit tests — the real thing working.

2. **Research** — read the feature README, check what exists vs what's needed. Identify the gap.

3. **Validate DoD** — is it testable? Specific enough? Can you verify it against the running system?

4. **Check resources** — services up? Env set? Hard blockers? If critical infra is down, report and stop.

5. **Build context** — read service READMEs from Code Ownership section. You now have full constraints.

Then move to DELIVER. No separate session. No nesting. You just keep going.

## DELIVER (you do the work)

Create a team (dev + validator). They work together in this session.

- **Dev** does the work — code, deploy, test
- **Validator** checks against business DoD — does the thing actually work? Not code review — run it and verify.

Stop hook keeps the session going until DoD passes or hard blocker.

**Validator gates state.** Dev produces output. Validator confirms it meets DoD. Only then does README State section update.

## SHOW

You tell the user what to verify. User does the thing. Works or doesn't.

## READMEs

Source of truth. Every feature/service README:

```
<!-- DESIGN: what we want -->
Why, Data Flow, Code Ownership, Constraints

---

<!-- STATE: what we got — updated after validation only -->
Quality Bar, Certainty, Known Issues
```

## Rules

- One session, no nesting, no backgrounding
- PLAN researches and validates DoD before coding
- DELIVER: dev + validator team, Stop hook enforces loop
- State only updated after validator confirms
- SHOW is the user doing the thing
