# Mission: Dissolve packages/ → services/ + true packages only

Focus: monorepo structure, build system, publishing
Problem: `packages/` contains 6 items but only 1 is a true reusable package (transcript-rendering). The rest (agent-api, meeting-api, runtime-api, transcription-service, tts-service) are standalone services that happen to have `pyproject.toml` — nobody pip-installs them externally. Meanwhile, the vexa Python API client lives in a separate repo (github.com/Vexa-ai/vexa-pypi-client) and should be in the monorepo.
Target: `packages/` = things published to registries (npm, PyPI). `services/` = everything deployed as containers. Monorepo publishes packages to npm/PyPI.
Stop-when: All services run, all cross-imports work, packages publish from monorepo. `make up` produces a working stack.
Constraint: No functional changes to any service. Pure restructure + publishing setup.

---

## Context: Why This Mission Exists

The `packages/` directory was created with the idea that agent-api and runtime-api would be published as standalone repos for community positioning. In practice:
- Nobody pip-installs these — they're deployed as Docker images
- The `pyproject.toml` files solve no real problem
- The real publishing needs are: npm (transcript-rendering) and PyPI (vexa-client API wrapper)
- vexa-pypi-client lives in a separate repo, drifting from the monorepo

### Current cross-boundary imports (CRITICAL — must not break)

All are `from meeting_api.*`, used because meeting-api is pip-installed in Dockerfiles:

| Consumer | Imports |
|----------|---------|
| services/api-gateway/main.py | `meeting_api.schemas`, `meeting_api.security_headers` |
| services/admin-api/app/main.py | `meeting_api.models`, `meeting_api.schemas`, `meeting_api.webhook_url` |
| services/calendar-service/app/main.py | `meeting_api.database`, `meeting_api.models` |
| services/calendar-service/app/models.py | `meeting_api.models` |
| services/calendar-service/app/sync.py | `meeting_api.models` |
| services/mcp/test_parse_meeting_url.py | `meeting_api.schemas` |

These imports work because Dockerfiles do `pip install /path/to/meeting-api`. This mechanism continues to work after the move — only the COPY path in Dockerfiles changes.

---

## Target Structure

```
packages/                          # Published to registries
  transcript-rendering/            # npm: @vexaai/transcript-rendering (already works)
  vexa-client/                     # PyPI: vexa-client (brought from external repo)

services/                          # Deployed as containers
  meeting-api/                     # ← from packages/ (keeps pyproject.toml for internal pip install)
  agent-api/                       # ← from packages/
  runtime-api/                     # ← from packages/
  transcription-service/           # ← from packages/
  tts-service/                     # ← from packages/
  admin-api/                       # (unchanged)
  api-gateway/                     # (unchanged)
  calendar-service/                # (unchanged)
  dashboard/                       # (unchanged)
  mcp/                             # (unchanged)
  vexa-bot/                        # (unchanged)
  vexa-agent/                      # (unchanged)
  telegram-bot/                    # (unchanged)
  transcript-rendering/            # DELETE — just dist/ artifacts, stale
  transcription-collector/         # DELETE — folded into meeting-api already
```

---

## Phase 1: Move packages → services

**Goal:** Relocate 5 Python services from packages/ to services/. Nothing breaks.

### Tasks

- [ ] `git mv services/agent-api services/agent-api`
- [ ] `git mv services/meeting-api services/meeting-api`
- [ ] `git mv services/runtime-api services/runtime-api`
- [ ] `git mv services/transcription-service services/transcription-service`
- [ ] `git mv services/tts-service services/tts-service`
- [ ] Delete stale `services/transcript-rendering/` (just dist/ artifacts)
- [ ] Delete stale `services/transcription-collector/` (folded into meeting-api)
- [ ] Update `deploy/compose/docker-compose.yml` — all `build.context` and `build.dockerfile` paths that reference `packages/`
- [ ] Update every Dockerfile that COPYs or pip-installs from `packages/` path:
  - api-gateway Dockerfile (installs meeting-api)
  - admin-api Dockerfile (installs meeting-api)
  - calendar-service Dockerfile (installs meeting-api)
  - meeting-api's own Dockerfile
  - agent-api's own Dockerfile
  - runtime-api's own Dockerfile
  - transcription-service's own Dockerfile
  - tts-service's own Dockerfile
- [ ] Grep for any remaining `packages/` path references in Makefiles, scripts, CI configs, .dockerignore
- [ ] `docker compose config` validates with no errors

---

## Phase 2: Bring in vexa-pypi-client

**Goal:** Import the vexa Python API wrapper into the monorepo as a publishable package.

### Tasks

- [ ] Clone/copy https://github.com/Vexa-ai/vexa-pypi-client into `packages/vexa-client/`
- [ ] Review and update `pyproject.toml` (or convert from `setup.py`) — package name `vexa-client`, version, deps
- [ ] Add a simple test: `python -c "from vexa_client import VexaClient; print('ok')"`

---

## Phase 3: Monorepo publishing setup

**Goal:** npm and PyPI packages publish from this repo.

### Tasks

- [ ] Verify transcript-rendering npm publish works (may already have workflow)
- [ ] Set up PyPI publishing for vexa-client (pyproject.toml with hatchling or setuptools, `python -m build` works)
- [ ] (Optional) GitHub Actions workflow for automated publishing on tag/release

---

## DoD

**Every item has an exact test.** No item is done until the test command runs and shows the expected output.

### Confidence = weighted DoD

Each item has a **weight** reflecting risk, and **min/max confidence bounds** — the range your overall confidence MUST stay within based on this item's pass/fail status.

| DoD | Weight | Max if FAIL | Min if PASS | Verify |
|-----|--------|-------------|-------------|--------|
| **D1. `docker compose build` passes** | **25** | **0** | 25 | `docker compose build` — zero errors. If this fails, nothing else matters. |
| **D2. Full stack runs** | **20** | **25** | 45 | `make up` — all containers healthy (`docker compose ps`, no restarts/exits). |
| **D3. Cross-imports work at runtime** | **15** | **30** | 60 | api-gateway, admin-api, calendar-service logs show no `ModuleNotFoundError` / `ImportError` for `meeting_api`. `curl /health` on each returns 200. |
| **D4. Dashboard + meetings functional** | **15** | **50** | 75 | Open dashboard, create meeting, verify bot lifecycle works end-to-end. Ceiling=50 without this — restructure could silently break runtime wiring (G4). |
| D5. Agent chat works | 5 | **70** | 80 | `curl POST /chat` to agent-api returns a streamed response. |
| D6. `packages/` is clean | 5 | 85 | 85 | `ls packages/` → only `transcript-rendering/`, `vexa-client/`. Nothing else. |
| D7. No stale path refs | 5 | 85 | 90 | `grep -rn "services/meeting-api\|services/agent-api\|services/runtime-api\|services/transcription-service\|services/tts-service" deploy/ services/ Makefile` → zero hits. |
| D8. vexa-client builds | 5 | 90 | 95 | `cd packages/vexa-client && python -m build` → produces `.whl` in `dist/`. |
| D9. transcript-rendering builds | 5 | 90 | 100 | `cd packages/transcript-rendering && npm pack` → produces `.tgz`. |
| | **= 100** | | | |

**How to read this table:**
- **Max if FAIL** = confidence ceiling when this item fails. D1 fail → can't exceed 0. D4 fail → can't exceed 50.
- **Min if PASS** = confidence floor once this item passes (cumulative). D1-D3 all pass → confidence is at least 60.

**Critical path (G11):** D1→D2→D3→D4 are sequential gates. No amount of passing D5-D9 compensates for a failing D1-D4. Structural checks (D6-D9) without a running system are meaningless.

---

## Risk Register

| Risk | Mitigation |
|------|-----------|
| Dockerfile COPY paths break after move | Phase 1 includes explicit Dockerfile updates + `docker compose config` validation |
| `from meeting_api` imports fail at runtime | meeting-api keeps pyproject.toml, still pip-installed in consumer Dockerfiles — just from new path |
| Stale `packages/` references in scripts | Grep sweep in Phase 1 catches them |
| vexa-pypi-client has diverged from current API | Phase 2 includes review — may need updates to match current API surface |
