# Conductor

## PLAN (this conversation)

1. **Acceptance criteria** — what does the user actually need to work? Not scores, not quality bars. Real thing: "I open the dashboard, click a meeting, see live transcripts." That's the gate.

2. **Resource check** — are the services needed for this actually running? Quick curl, docker ps. If something critical is down, say so and stop. Don't launch into a broken environment.

3. **Build prompt file** — mission + feature README + service READMEs → `batches/{name}-prompt.txt`

4. **Give the user the command:**
```bash
CONDUCTOR_MISSION={name} claude --worktree {name} \
    --append-system-prompt-file conductor/batches/{name}-prompt.txt
```

## DELIVER (user runs the command)

Interactive Claude session. User sees everything. Stop hook keeps it going.

Inside the session, a team:
- **Dev** does the work
- **Evaluator** checks: are we meeting the REAL acceptance criteria? Not "code looks right" — actually run it and verify. If dev claims "fixed" but the dashboard still shows stale data, evaluator rejects.

The loop: dev works → evaluator checks against acceptance criteria → not met → dev continues. Stop hook enforces this. Session doesn't end until acceptance criteria pass or hard blocker (infra down, missing credentials, needs human action).

## SHOW (user validates)

User checks it themselves. Opens the dashboard. Clicks the meeting. Sees live transcripts. Either it works or it doesn't. No scores, no findings — just: does the thing work?

## Rules

- Acceptance criteria are from the user, in their words
- PLAN only checks resources, doesn't fix them
- DELIVER never exits until criteria met or hard blocker
- SHOW is the user doing the thing, not an agent claiming it works
