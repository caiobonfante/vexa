# /conductor-entry — Ritualized session startup for conductor-spawned sessions

Read all state files in order. Print a structured summary. This is your FIRST action in every conductor-spawned session.

## Steps

### 1. Read mission
```bash
cat conductor/mission.md
```

### 2. Read conductor state
```bash
cat conductor/state.json
```

### 3. Read system findings
```bash
cat features/tests/findings.md
```

### 4. Read orchestrator history
```bash
cat features/orchestrator-log.md | tail -80
```

### 5. Read tool confidence
```bash
cat features/tools/README.md
```

### 6. Read recent git history
```bash
git log --oneline -10
```

## After reading

Print a brief summary:
- **Mission**: {focus} — {problem}
- **Iteration**: {N}
- **Key blockers**: {from findings/orchestrator-log}
- **Plan**: {what you'll do this iteration}

Then execute the mission. Do not wait for confirmation.
