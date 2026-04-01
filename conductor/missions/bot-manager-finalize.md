# Mission

Focus: bot-manager → meeting-api finalization
Problem: Phase 4 deleted bot-manager source but left ~99 files with stale references, a confusing legacy env var, and dead deploy configs
Target: Zero stale bot-manager references (except frozen contracts), env var renamed, dead configs cleaned
Stop-when: all phases addressed AND full stack deploys AND every affected route verified by curl AND grep finds only frozen-contract references AND Playwright dashboard tests pass AND zero bot-manager in code/docs (except frozen contracts)

## Context

Phase 4 (commit `65f033d3`) deleted `services/bot-manager/` and created `services/meeting-api` + `services/runtime-api`. The structural refactoring is done — all endpoints are ported or intentionally stubbed (deferred transcription = 501). The remaining work is naming cleanup.

**Verified non-gaps** (investigated and confirmed NOT missing):
- Agent Chat → routes to `agent-api`, never was meeting-api's job
- Browser Session Token Resolution → gateway resolves via Redis directly, no HTTP endpoint needed
- Browser Session Storage Sync → already ported (`POST /internal/browser-sessions/{token}/save`)
- Workspace Git Config → routes to `admin-api`, never was meeting-api's job
- Deferred Transcription → intentional 501 stub, acceptable for now

## Phase 1 — Rename env var BOT_MANAGER_URL → MEETING_API_URL

The most impactful change. ~15 files, ~40 line changes.

**Core code (4 files):**
1. `services/api-gateway/main.py` — 24 occurrences: env load, startup validation, ~20 route handlers
2. `services/calendar-service/app/sync.py` — 2 occurrences: env load, bot POST call
3. `services/api-gateway/tests/conftest.py` — 1 occurrence: test env setup
4. ~~Backward compat~~ — NO. Clean rename: `BOT_MANAGER_URL` → `MEETING_API_URL` everywhere, no fallback

**Config files (4 files):**
5. `deploy/compose/docker-compose.yml` — 1 occurrence
6. `features/agentic-runtime/deploy/docker-compose.yml` — 2 occurrences (gateway + calendar-service)
7. `deploy/helm/charts/vexa/templates/deployment-api-gateway.yaml` — 1 occurrence (also fix: currently points to transcription-collector, should be meeting-api)
8. `.github/workflows/test-api-gateway.yml` — 1 occurrence

**Docs to update after rename:**
9. `services/api-gateway/README.md`
10. `features/agentic-runtime/PORT-MAP.md`
11. `features/post-meeting-transcription/tests/Makefile` + `.env.example`

## Phase 2 — Clean stale references in source code

12. `services/vexa-bot/core/src/` — TypeScript comments referencing bot-manager. Update to meeting-api
13. `services/admin-api/app/main.py` — comments: "Reuse logic from bot-manager", "Copied from bot-manager"
14. `services/meeting-api/meeting_api/*.py` — internal comments still say "bot-manager". Update (except frozen contract notes in webhook_url.py)
15. `services/vexa-bot/hot-run.sh` — dev script URL replacement references bot-manager
16. `scripts/build-clean.sh` — cleanup references to deleted directory

## Phase 3 — Clean stale references in docs

17. Feature READMEs still referencing bot-manager (~15 files in features/)
18. `services/api-gateway/README.md`, `services/meeting-api/README.md`
19. `docs/*.mdx` files (external-facing docs)
20. Test findings files (`**/tests/findings.md`)
21. Conductor missions and evaluator verdicts that reference bot-manager

## Phase 4 — Dead deploy cleanup (LOW PRIORITY)

`deploy/lite/` is unused — not referenced by any active docker-compose, CI, or Makefile. But if we keep it:

22. `deploy/lite/Dockerfile.lite` — `COPY services/bot-manager/app/` references deleted directory
23. `deploy/lite/supervisord.conf` — `[program:bot-manager]` block for non-existent service
24. `features/agentic-runtime/deploy/check-env.sh` — checks for `vexa-agentic-bot-manager` container

Alternative: delete or archive `deploy/lite/` entirely if it's abandoned.

## Frozen contracts (DO NOT RENAME)

- `services/meeting-api/meeting_api/webhook_url.py` — JWT issuer list includes `"bot-manager"` (legacy tokens still in circulation)
- Redis channel prefix `bm:` — frozen, used by vexa-bot and meeting-api
- `/bots/*` API paths — frozen external contract
- NO fallback env var — `BOT_MANAGER_URL` is dead, replaced everywhere by `MEETING_API_URL`

## DoD — Definition of Done

### 1. Stack deploys clean
- `docker compose config` validates for `features/agentic-runtime/deploy/`
- `docker compose up -d` succeeds — all services healthy
- api-gateway starts with `MEETING_API_URL` env var (no fallback — `BOT_MANAGER_URL` is dead)
- `docker compose logs api-gateway` shows `MEETING_API_URL` loaded, zero references to `BOT_MANAGER_URL`
- Helm: `grep "MEETING_API_URL" deploy/helm/charts/vexa/templates/deployment-api-gateway.yaml` returns the correct value pointing to meeting-api (NOT transcription-collector)

### 2. Bot lifecycle routes work (gateway → meeting-api)
These routes all proxy through `MEETING_API_URL`. Verify each with curl against gateway (:8056 or :8066):

**Bot CRUD (auth: X-API-Key with "bot" scope):**
- `GET /bots/status` → 200, returns `{"running_bots": [...]}`
- `POST /bots` with `{"platform":"google_meet","native_meeting_id":"test-xxx","bot_name":"test"}` → 201 or 4xx (valid response from meeting-api, NOT 502/503)
- `DELETE /bots/google_meet/test-xxx` → 200 or 404 (valid response, NOT 502)
- `PUT /bots/google_meet/test-xxx/config` → 200 or 404 (valid response, NOT 502)

**Voice agent (auth: X-API-Key with "bot" scope):**
- `POST /bots/google_meet/test-xxx/speak` → valid response (NOT 502)
- `DELETE /bots/google_meet/test-xxx/speak` → valid response (NOT 502)
- `POST /bots/google_meet/test-xxx/chat` → valid response (NOT 502)
- `GET /bots/google_meet/test-xxx/chat` → valid response (NOT 502)
- `POST /bots/google_meet/test-xxx/screen` → valid response (NOT 502)
- `DELETE /bots/google_meet/test-xxx/screen` → valid response (NOT 502)
- `PUT /bots/google_meet/test-xxx/avatar` → valid response (NOT 502)
- `DELETE /bots/google_meet/test-xxx/avatar` → valid response (NOT 502)

**Recordings (auth: X-API-Key with "tx" scope):**
- `GET /recordings` → 200, returns list (empty OK)
- `GET /recordings/{id}` → 200 or 404 (valid response, NOT 502)
- `GET /recordings/{id}/media/{media_id}/download` → valid response (NOT 502)
- `GET /recordings/{id}/media/{media_id}/raw` → valid response (NOT 502)
- `DELETE /recordings/{id}` → valid response (NOT 502)
- `GET /recording-config` → 200, returns config object
- `PUT /recording-config` with `{"enabled": true}` → 200

**Transcription:**
- `POST /meetings/99999/transcribe` → 501 "not yet implemented" (intentional stub, NOT 502)

**Internal routes (no auth — internal network only):**
- `POST /internal/browser-sessions/{token}/save` → valid response (NOT 502)
- `DELETE /internal/browser-sessions/{user_id}/storage` → valid response (NOT 502)

**"NOT 502" is the key signal.** 502 = gateway can't reach meeting-api = env var rename broke routing. Any other status (200, 400, 404, 501) means the route is wired correctly.

### 3. Calendar service wired correctly
- `docker compose logs calendar-service` shows it loaded `MEETING_API_URL` (not `BOT_MANAGER_URL`)
- If calendar sync is active: logs show `POST http://meeting-api:8080/bots` calls (not bot-manager)

### 4. API contracts preserved
- `/bots/*` paths still work — external clients see no change
- JWT issuer `"bot-manager"` still accepted in `webhook_url.py` and `processors.py`
- Redis channel prefix `bm:` unchanged
- `POST /api/chat` context helper fetches `/bots/status` from meeting-api (check gateway logs for upstream URL)

### 5. Grep is clean
- `grep -rn "BOT_MANAGER_URL" --include="*.py" --include="*.ts" --include="*.yml" --include="*.yaml"` returns **zero results** (no fallback — it's dead)
- `grep -rn "bot.manager" --include="*.py" --include="*.ts" --include="*.sh"` returns only frozen contracts (JWT issuer `"bot-manager"`, `bm:` prefix notes)

### 6. Dashboard works — Playwright E2E
- Run `features/auth-and-limits/tests/dashboard.spec.ts` via `/test-dashboard-auth`
- All 8 tests pass: login, profile page, API key create/revoke, scope badges, meeting endpoint
- Dashboard loads at gateway URL — not just "loads" but full auth flow verified

### 7. No regressions
- Existing bot (if any running) still reports status via `GET /bots/status`
- WebSocket fan-out still works (gateway subscribes to `bm:meeting:*` Redis channels — frozen prefix)

### 8. Zero bot-manager in code and docs
- `grep -rn "bot.manager" --include="*.py" --include="*.ts" --include="*.js" --include="*.sh" --include="*.md" --include="*.mdx" --include="*.yml" --include="*.yaml"` returns ONLY:
  - Frozen contracts: JWT issuer `"bot-manager"` in webhook_url.py and processors.py
  - Frozen contracts: `bm:` prefix references
  - This mission file itself
- **Nothing else.** No comments saying "copied from bot-manager", no docs referencing "bot-manager service", no stale env var names. Clean.
