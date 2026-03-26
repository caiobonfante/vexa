# Service Port Map — Vexa Agentic Runtime

Single source of truth for all service ports and environment variables.
Generated: 2026-03-24. Update this file whenever ports or env vars change.

---

## Port Map

| Service | Container Port | Host Port | Compose Env Var | Notes |
|---------|---------------|-----------|-----------------|-------|
| api-gateway | 8000 | **8066** | `API_GATEWAY_PORT` | Main entry point for dashboard + external clients |
| admin-api | 8001 | **8067** | `ADMIN_API_PORT` | User/token management; requires `X-Admin-API-Key` header |
| agent-api | 8100 | **8100** | `CHAT_API_PORT` | Chat/agent sessions; requires `X-API-Key: BOT_API_TOKEN` |
| runtime-api | 8090 | **8090** | `RUNTIME_API_PORT` | Container lifecycle; internal to compose network |
| bot-manager | 8080 | **8070** | `BOT_MANAGER_PORT` | Meeting bot orchestration; internal to compose network |
| transcription-collector | 8000 | **8060** | `TC_PORT` | Transcript storage/retrieval; internal to compose network |
| redis | 6379 | **6389** | `REDIS_PORT` | WARNING: host port is NOT 6379. Use 6389 from host. |
| postgres | 5432 | **5458** | `POSTGRES_PORT` | WARNING: host port is NOT 5432. Use 5458 from host. |
| minio API | 9000 | **9010** | `MINIO_PORT` | Object storage API. WARNING: host port is NOT 9000. |
| minio console | 9001 | **9011** | `MINIO_CONSOLE_PORT` | MinIO web UI |
| telegram-bot | 8200 | (internal only) | — | No host binding; webhook only |
| calendar-service | 8050 | **8050** | `CALENDAR_SERVICE_PORT` | Calendar sync + bot scheduling; optional service |

**Critical: redis and postgres host ports are offset from their defaults.**
Any tool, test, or script connecting from the host must use 6389 (redis) and 5458 (postgres).

---

## Service-to-Service Communication

All inter-service calls use **container names** (not localhost). Services are on the `vexa_agentic` Docker network.

| Caller | Target | URL Used | Token |
|--------|--------|----------|-------|
| api-gateway | admin-api | `http://admin-api:8001` | passes through user token |
| api-gateway | bot-manager | `http://bot-manager:8080` | passes through user token |
| api-gateway | transcription-collector | `http://transcription-collector:8000` | passes through user token |
| bot-manager | agent-api | `http://agent-api:8100` | `POST_MEETING_HOOKS` webhook |
| agent-api | runtime-api | `http://runtime-api:8090` | `BOT_API_TOKEN` |
| telegram-bot | agent-api | `http://agent-api:8100` | no auth (internal) |
| dashboard (Next.js server) | api-gateway | `http://localhost:8066` | user JWT token |
| dashboard (Next.js server) | agent-api | `http://localhost:8100` | `AGENT_API_TOKEN` |
| dashboard (Next.js server) | admin-api | `http://localhost:8067` | `VEXA_ADMIN_API_KEY` |
| calendar-service | bot-manager | `http://bot-manager:8080` | `BOT_API_TOKEN` as `X-API-Key` |
| api-gateway | calendar-service | `http://calendar-service:8050` | passes through user token |

---

## Environment Variable Reference

### Compose-level variables (set in `deploy/.env`)

| Variable | Default | Required | Notes |
|----------|---------|----------|-------|
| `BOT_API_TOKEN` | — | **YES** | Service-to-service auth. Must match `AGENT_API_TOKEN` in dashboard. |
| `TRANSCRIPTION_SERVICE_URL` | — | YES for bots | External transcription service URL (e.g. `http://172.17.0.1:8083`) |
| `TRANSCRIPTION_SERVICE_TOKEN` | `` | NO | Token for transcription service; empty OK if service has no auth |
| `TELEGRAM_BOT_TOKEN` | — | YES for Telegram | Telegram bot API token |
| `CLAUDE_CREDENTIALS_PATH` | — | YES for agents | Path to Claude Code credentials file on host (mounted into containers) |
| `CLAUDE_JSON_PATH` | — | YES for agents | Path to claude.json on host |
| `CHAT_DEFAULT_USER_ID` | — | NO | Default user ID for Telegram messages without mapping |
| `CHAT_USER_MAP` | `{}` | NO | JSON map of Telegram user IDs to internal user IDs |
| `ADMIN_TOKEN` | `vexa-admin-token` | YES | Shared admin token; must match across bot-manager, admin-api |
| `DB_NAME` | `vexa_agentic` | NO | Postgres database name |
| `DB_USER` | `postgres` | NO | Postgres user |
| `DB_PASSWORD` | `postgres` | NO | Postgres password |
| `MINIO_ACCESS_KEY` | `vexa-access-key` | NO | MinIO access key |
| `MINIO_SECRET_KEY` | `vexa-secret-key` | NO | MinIO secret key |
| `MINIO_BUCKET` | `vexa-agentic` | NO | MinIO bucket name |
| `LOG_LEVEL` | `INFO` | NO | Log verbosity for all services |
| `REDIS_PORT` | `6389` | NO | Host-side redis port |
| `POSTGRES_PORT` | `5458` | NO | Host-side postgres port |

### Per-service environment variables

#### api-gateway
| Variable | Value in container | Source |
|----------|--------------------|--------|
| `ADMIN_API_URL` | `http://admin-api:8001` | hardcoded in compose |
| `BOT_MANAGER_URL` | `http://bot-manager:8080` | hardcoded in compose |
| `TRANSCRIPTION_COLLECTOR_URL` | `http://transcription-collector:8000` | hardcoded in compose |
| `MCP_URL` | `http://mcp:18888` | hardcoded in compose (mcp service not in stack) |
| `REDIS_URL` | `redis://redis:6379/0` | hardcoded in compose |
| `CORS_ORIGINS` | `http://localhost:3002,http://localhost:3001` | hardcoded in compose |

**Note:** `MCP_URL` references a service not in the compose stack. api-gateway handles missing MCP gracefully.

#### admin-api
| Variable | Value in container | Source |
|----------|--------------------|--------|
| `ADMIN_API_TOKEN` | `vexa-admin-token` | from `ADMIN_TOKEN` in .env |
| `DB_*` | postgres credentials | from .env |

**Note:** admin-api uses `ADMIN_API_TOKEN`; bot-manager uses `ADMIN_TOKEN` — these are different env var names but must have the same value.

#### agent-api
| Variable | Value in container | Source |
|----------|--------------------|--------|
| `BOT_API_TOKEN` | from .env | service-to-service auth token |
| `REDIS_URL` | `redis://redis:6379` | hardcoded in compose |
| `RUNTIME_API_URL` | `http://runtime-api:8090` | hardcoded in compose |
| `MINIO_ENDPOINT` | `http://minio:9000` | **includes http://** — intentional for boto3 |
| `CLAUDE_CREDENTIALS_PATH` | from .env | mounted host path |
| `CLAUDE_JSON_PATH` | from .env | mounted host path |

#### runtime-api
| Variable | Value in container | Source |
|----------|--------------------|--------|
| `REDIS_URL` | `redis://redis:6379` | hardcoded in compose |
| `MINIO_ENDPOINT` | `minio:9000` | **no http://** — used as host:port for minio client |
| `BOT_API_TOKEN` | from .env | auth for vexa CLI calls from agent containers |
| `DOCKER_NETWORK` | `vexa-agentic_vexa_agentic` | compose project prefix + network name |

**Note:** MINIO_ENDPOINT format differs between runtime-api (`minio:9000`) and agent-api (`http://minio:9000`). This is intentional — each service uses a different MinIO client library with different URL expectations.

#### bot-manager
| Variable | Value in container | Source |
|----------|--------------------|--------|
| `REDIS_URL` | `redis://redis:6379/0` | hardcoded in compose |
| `DOCKER_NETWORK` | `vexa-agentic_vexa_agentic` | hardcoded in compose |
| `MINIO_ENDPOINT` | `minio:9000` | **no http://** |
| `ADMIN_TOKEN` | `vexa-admin-token` | from .env |
| `TRANSCRIPTION_SERVICE_URL` | from .env | external service; use host IP not `localhost` |
| `POST_MEETING_HOOKS` | `http://agent-api:8100/internal/webhooks/meeting-completed` | hardcoded in compose |
| `TTS_SERVICE_URL` | `http://tts-service:8002` | default; tts-service not in this stack |

#### transcription-collector
| Variable | Value in container | Source |
|----------|--------------------|--------|
| `REDIS_HOST` | `redis` | hardcoded in compose (uses REDIS_HOST/PORT, not REDIS_URL) |
| `REDIS_PORT` | `6379` | container-internal port, not host port |
| `MINIO_ENDPOINT` | `minio:9000` | no http:// |
| `ADMIN_TOKEN` | `vexa-admin-token` | from .env |

**Note:** transcription-collector uses `REDIS_HOST` + `REDIS_PORT` (not `REDIS_URL`). This is inconsistent with other services but working.

### Dashboard variables (set in `services/dashboard/.env`)

| Variable | Set? | Where used | Notes |
|----------|------|-----------|-------|
| `VEXA_API_URL` | YES (`http://localhost:8066`) | server-side API calls, config endpoint | Main API gateway URL |
| `VEXA_ADMIN_API_URL` | YES (`http://localhost:8067`) | admin operations | Direct admin-api access |
| `VEXA_ADMIN_API_KEY` | YES (`vexa-admin-token`) | admin API calls | Must match `ADMIN_TOKEN` in compose |
| `AGENT_API_URL` | YES (`http://localhost:8100`) | `/api/agent/` proxy route | Server-side proxy to agent-api |
| `AGENT_API_TOKEN` | YES (matches `BOT_API_TOKEN`) | `/api/agent/` proxy route | Must match `BOT_API_TOKEN` in compose .env |
| `TC_URL` | YES (`http://localhost:8060`) | transcript retrieval | Direct transcription-collector access |
| `NEXT_PUBLIC_VEXA_WS_URL` | YES (`ws://localhost:8066/ws`) | client-side WebSocket | Live transcript streaming |
| `NEXT_PUBLIC_APP_URL` | YES (`http://localhost:3002`) | Next.js app URL | |
| `NEXTAUTH_URL` | YES (`http://localhost:3002`) | NextAuth callbacks | |
| `NEXTAUTH_SECRET` | YES | session signing | |
| `JWT_SECRET` | YES | JWT signing | |
| `ENABLE_GOOGLE_AUTH` | YES (`false`) | OAuth toggle | |

**Missing NEXT_PUBLIC_ vars** (referenced in source but not set — all have safe fallbacks):

| Variable | Fallback behavior | Action needed? |
|----------|------------------|----------------|
| `NEXT_PUBLIC_AGENT_API_URL` | Falls back to `/api/agent` (server-side proxy) | NO — proxy route handles it |
| `NEXT_PUBLIC_VEXA_API_URL` | Falls back to `VEXA_API_URL` via config endpoint | NO — config route handles it |
| `NEXT_PUBLIC_VEXA_PUBLIC_API_URL` | Falls back to `VEXA_API_URL` | NO |
| `NEXT_PUBLIC_HOSTED_MODE` | Defaults to `false` | NO |
| `NEXT_PUBLIC_WEBAPP_URL` | Defaults to `https://vexa.ai` | NO |
| `NEXT_PUBLIC_TRANSCRIPT_SHARE_BASE_URL` | Not set | Only needed for share feature |
| `NEXT_PUBLIC_BASE_URL` / `NEXT_PUBLIC_BASE_PATH` | Not set | Only needed for hosted mode |
| `NEXT_PUBLIC_TRACKER_ENABLED` | Defaults to disabled | NO |

---

## Known Inconsistencies (by design, not bugs)

1. **MINIO_ENDPOINT format**: agent-api uses `http://minio:9000`; runtime-api, bot-manager, transcription-collector use `minio:9000`. Each service's MinIO client library requires a different format. Do not "fix" this by making them uniform — it will break one or the other.

2. **REDIS_URL vs REDIS_HOST+REDIS_PORT**: transcription-collector uses `REDIS_HOST`/`REDIS_PORT`; all other services use `REDIS_URL`. Both work. Do not unify unless you update transcription-collector source.

3. **ADMIN_TOKEN vs ADMIN_API_TOKEN**: bot-manager reads `ADMIN_TOKEN`; admin-api reads `ADMIN_API_TOKEN`. The compose file maps the same value correctly (`ADMIN_TOKEN=${ADMIN_TOKEN:-vexa-admin-token}` → container env `ADMIN_TOKEN`; admin-api compose env: `ADMIN_API_TOKEN=${ADMIN_TOKEN:-vexa-admin-token}`). Same value, different names.

4. **Host ports offset from container ports**: redis (6389≠6379), postgres (5458≠5432), minio (9010≠9000). This avoids conflicts with other stacks on the same host.

5. **MCP_URL unreachable**: api-gateway has `MCP_URL=http://mcp:18888` but no mcp service is in this compose stack. api-gateway handles missing MCP gracefully (routes return 503 rather than crashing).
