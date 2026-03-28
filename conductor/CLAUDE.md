# Conductor

How to run a mission. Three steps.

## 1. PLAN (this conversation)

```
Read feature README → score, quality bar, constraints
Quick resource check → services up? env set?
Create missions/{name}.md
Build batches/{name}-prompt.txt:
    cat missions/{name}.md > batches/{name}-prompt.txt
    cat features/{focus}/README.md >> batches/{name}-prompt.txt
    # append service READMEs from Code Ownership section
```

## 2. DELIVER (user runs this)

```bash
CONDUCTOR_MISSION={name} claude --worktree {name} \
    --append-system-prompt-file conductor/batches/{name}-prompt.txt
```

One terminal. Interactive. User sees everything. Stop hook keeps it going until target met.

## 3. EVALUATE (this or any conversation)

Review what changed. Merge or reject.

## Rules

- PLAN is read-only — no code edits
- Prompt file has feature README + service READMEs + mission
- Stop hook fires on CONDUCTOR_MISSION env var only
- User runs delivery themselves — never nest claude inside claude
