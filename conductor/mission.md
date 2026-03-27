# Mission

Focus: system-architecture
Problem: Incomplete refactoring left stale duplicates, broken references, and architectural confusion between packages/ and services/
Target: Zero stale code, all deployment configs reference correct paths, everything builds and runs
Stop-when: all items below addressed AND `docker compose up` succeeds AND `make migrate` succeeds
Constraint: Never delete anything that's actually imported/deployed — verify before removing

## Phase 1 — Delete dead code

1. `rm -rf services/agent-api/` — legacy duplicate, not in docker-compose, diverged from packages/ version
2. `rm -rf services/transcript-rendering/` — exact duplicate of packages/transcript-rendering/, dashboard imports from packages/
3. `rm -rf services/transcription-collector/` — folded into meeting-api (commit cdaa69e5), only __pycache__ remains
4. `rm replay_transcript.py` — orphaned root-level script with hardcoded credentials, zero references

## Phase 2 — Fix broken references

5. `deploy/compose/Makefile` — replace all `transcription-collector` service references with `meeting-api` (lines 124-175)
6. Helm charts — delete `deployment-bot-manager.yaml`, `service-bot-manager.yaml`, update `values.yaml` to remove botManager section, update api-gateway template to not reference bot-manager
7. Root `alembic.ini` — either delete (real migrations are in libs/shared-models/) or add a comment redirecting to the correct location

## Phase 3 — Update stale documentation

8. Root `README.md` — remove references to bot-manager and transcription-collector, update service table to reflect packages/ vs services/ split
9. `services/README.md` — update to reflect that agent-api, transcript-rendering, transcription-collector are gone; note that meeting-api, runtime-api, transcription-service, tts-service live in packages/

## Phase 4 — Clean build artifacts

10. Remove all `__pycache__/` and `.pytest_cache/` directories from version control (they should be gitignored)
11. Verify `.gitignore` covers `__pycache__/`, `.pytest_cache/`, `node_modules/`, `dist/` appropriately

## Phase 5 — Verify everything works

12. `cd deploy/compose && docker compose config` — validates compose file syntax
13. `cd deploy/compose && docker compose build` — everything builds
14. Run existing tests to confirm nothing broke
15. `git diff --stat` to review all changes before committing

## Success criteria

- `ls services/` shows only: admin-api, api-gateway, calendar-service, dashboard, mcp, telegram-bot, vexa-agent, vexa-bot, README.md, redis.md
- `ls packages/` unchanged (agent-api stays — it's the canonical version even if not deployed yet)
- No file in the repo imports from services/agent-api, services/transcript-rendering, or services/transcription-collector
- docker-compose config validates
- docker-compose build succeeds
