# /test [mode] — Compose deployment test tree

Cascading test: compose → infra → services → integrations. Each level triggers the next, findings bubble up.

## Modes
- `quick` — containers up + endpoints respond (~2 min)
- `standard` — quick + API functionality + DB checks (~10 min) [default]
- `full` — standard + deep service agents in waves (~30 min)

## Phase 1: Build + Start
- `make down 2>/dev/null; rm -f .env; make all`
- Verify: `make ps` shows all containers Up, 0 restarts
- If fails: STOP, report build failure

## Phase 2: Infrastructure (compose agent runs directly)
Test each infra component. Read infra/*.md for specs.
- **Redis:** PING, xlen transcription_segments, consumer groups exist
- **Postgres:** pg_isready, vexa DB exists, alembic_version table, 7 core tables present, zero FK orphans
- **MinIO:** health endpoint, vexa-recordings bucket exists
- Save findings per component

## Phase 3: Service health (compose agent runs directly)
For each service in "What working means":
- curl endpoint, expect specific status code
- Check docker logs for fatal/panic/error
- Check restart count = 0

## Phase 4: API functionality (compose agent, standard+full only)
- Create test user (POST /admin/users)
- Create API token (POST /admin/users/{id}/tokens)
- List meetings (GET /meetings)
- Create bot dry-run (POST /bots — expect 400 for invalid meeting)
- Check bot status (GET /bots/status)
- Clean up test data

## Phase 5: Deep service testing (full mode only)
Dispatch background agents in waves (max 3 concurrent):

**Wave 1:** (foundation services)
- admin-api agent: "Test admin-api. Docker Compose stack is running on localhost. Read services/admin-api/.claude/CLAUDE.md and README.md. Curl localhost:8057. Save findings to services/admin-api/tests/findings.md"
- transcription-collector agent: same pattern, localhost:8123
- shared-models agent: verify models match DB schema, check alembic

**Wave 2:** (dependent services)
- bot-manager agent: localhost:8080 (internal, test via gateway proxy at 8056)
- api-gateway agent: localhost:8056, verify all proxy routes
- mcp agent: localhost:18888

**Wave 3:** (frontend + optional)
- dashboard agent: localhost:3001
- tts-service agent: verify available

Each agent:
1. Reads its .claude/CLAUDE.md for scope and critical questions
2. Reads its README.md "What working means" / "Known limitations" for specs
3. Tests everything it can via curl + file inspection
4. Saves findings.md with PASS/FAIL/DEGRADED/UNTESTED/SURPRISING
5. Updates README if specs were unclear

## Phase 6: Aggregate
- Read all services/*/tests/findings.md
- Count totals: PASS, FAIL, DEGRADED, UNTESTED, SURPRISING
- Flag cross-service issues (e.g., gateway says proxy works but backend says it crashed)
- Update deploy/compose/README.md "What working means" if any spec was wrong

## Phase 7: Report
Save to deploy/compose/tests/results/report-{timestamp}.md:
- Mode, duration, date
- Summary: X pass / Y fail / Z degraded / W untested
- Critical findings (not just failures — what's risky, what surprised, what degraded)
- Per-service breakdown with links to findings.md
- Iteration: if failures found, note what to fix and re-run

## Iteration
If phase 5 finds failures:
1. Report which services failed
2. Suggest fixes (from the service agent's findings)
3. After human fixes, re-run only the failed wave
4. Re-aggregate
