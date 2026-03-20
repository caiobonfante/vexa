# /env-setup — Configure and verify infrastructure for a feature

You are in **Stage 0: ENV SETUP**. Your job is to get the infrastructure running and verified so the feature has a working environment to test against.

Read the full stage protocol: `features/README.md` (section: Stage 0: ENV SETUP)
Read the glossary: `features/README.md` (section: Glossary)

## Your constraints

- Do NOT change pipeline code — you are setting up infra, not developing
- Do NOT start a collection run or replay — verify infra first
- Do NOT assume previous infra is still valid — always re-verify
- Do NOT mix infra from different stacks

## Procedure

### 1. Identify the feature

Determine which feature you're setting up. Look for:
- The current working directory (are we inside a `features/{name}/` tree?)
- Recent conversation context
- Ask the user if ambiguous

Read the feature's:
- `features/{name}/.claude/CLAUDE.md` — scope, gate, what services are needed
- `features/{name}/README.md` — what components this feature uses
- `features/{name}/.env.example` — what config variables exist

### 2. Check for collection manifest

If entering from EXPAND, read the **collection manifest** in `features/{name}/tests/` — it specifies infra requirements. The `.env` must match those requirements.

### 3. Create or verify .env

Check if `features/{name}/.env` exists.

**If it doesn't exist:**
- Copy `.env.example` to `.env`
- Ask the user for actual values (tokens, URLs, ports) for their environment
- Fill in the values

**If it exists:**
- Read it and display the current config
- If a collection manifest exists, compare `.env` values against the manifest's infra requirements table
- Flag any mismatches

### 4. Start services

Based on the `.env`, determine what needs to be running:
- Check which services are already up (`docker ps`, health endpoints)
- Start what's missing (`make up` from `deploy/compose/`, transcription service, etc.)
- Wait for services to be ready

### 5. Verify each service

For every service endpoint in the `.env`, run a health check:

| Service | How to check |
|---------|-------------|
| Transcription service | `curl $TRANSCRIPTION_URL/../health` or send a tiny WAV |
| Redis | `redis-cli -u $REDIS_URL PING` |
| Postgres | `psql $POSTGRES_URL -c 'SELECT 1'` |
| TTS service | `curl $TTS_URL/../health` |
| API Gateway | `curl $API_GATEWAY_URL/health` |

Report each result: service name, expected version/config, actual result.

### 6. Run smoke test

Run `make smoke` from `features/{name}/tests/` (or equivalent):
- This sends one utterance through the full pipeline
- If it passes, infra is working end-to-end
- If it fails, diagnose which service in the chain broke

### 7. Record infra snapshot

Write `features/{name}/tests/infra-snapshot.md` with:
- Date
- Full `.env` contents (redact tokens to `{set, length N}`)
- Service verification results (health check outputs)
- Smoke test result

### 8. Report

Tell the user:
- Which services are running and verified
- Any issues found
- What stage to enter next:
  - If **collected data** exists → ready for SANDBOX ITERATION
  - If no **collected data** → ready for COLLECTION RUN
  - If **collection manifest** exists → ready for COLLECTION RUN

Log: `STAGE: env-setup complete — {N} services verified, infra snapshot saved at features/{name}/tests/infra-snapshot.md`
