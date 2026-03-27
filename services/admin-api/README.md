# Admin API

## Why

Users and API tokens must be managed independently of the bot lifecycle. Without a dedicated user management service, every service would need its own auth logic and direct DB access for user operations. The admin-api centralizes user CRUD, token generation/revocation, and analytics queries behind a single authenticated API, keeping the rest of the system stateless with respect to user identity.

## What

A FastAPI service that manages users, API tokens, and platform analytics. It is the only service that writes to the `users` and `api_tokens` tables.

### Documentation
- [Self-Hosted Management](../../docs/self-hosted-management.mdx)
- [Settings API](../../docs/api/settings.mdx)

Three routers provide different access levels:
- **Admin router** (`/admin/*`) -- full CRUD, requires `X-Admin-API-Key` header matching `ADMIN_API_TOKEN`
- **Analytics router** (`/admin/*` read-only subset) -- accepts either admin or analytics token
- **User router** (`/user/*`) -- self-service endpoints authenticated by the user's own `X-API-Key`

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/users` | Find or create a user by email (idempotent) |
| GET | `/admin/users` | List all users (paginated) |
| GET | `/admin/users/{user_id}` | Get user by ID (includes API tokens) |
| GET | `/admin/users/email/{email}` | Get user by email |
| PATCH | `/admin/users/{user_id}` | Update user fields (name, image, max_concurrent_bots, data) |
| POST | `/admin/users/{user_id}/tokens?scope=user` | Generate a new API token for a user (scope: `user`, `bot`, `tx`, `admin`) |
| DELETE | `/admin/tokens/{token_id}` | Revoke an API token |
| GET | `/admin/stats/meetings-users` | Paginated meetings joined with user info |
| GET | `/admin/analytics/users` | User table (no sensitive fields) |
| GET | `/admin/analytics/meetings` | Meeting table (no sensitive fields) |
| GET | `/admin/analytics/meetings/{id}/telematics` | Session, transcription stats, performance metrics for a meeting |
| GET | `/admin/analytics/users/{id}/details` | Full user analytics: meeting stats, usage patterns |
| PUT | `/user/webhook` | Set webhook URL for the authenticated user |

### Dependencies

- **PostgreSQL** -- `users`, `api_tokens`, `meetings`, `meeting_sessions`, `transcriptions` tables via `shared_models`
- **shared_models** -- ORM models, schemas, database session factory, token scope utilities

## How

### Run

```bash
# Via docker-compose (from repo root)
docker compose up admin-api

# Standalone (from repo root, with venv active)
cd services/admin-api
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### Configure

| Variable | Description |
|----------|-------------|
| `ADMIN_API_TOKEN` | Secret token required in `X-Admin-API-Key` header for admin endpoints |
| `ANALYTICS_API_TOKEN` | Optional read-only token accepted by analytics endpoints |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | PostgreSQL connection |
| `DB_SSL_MODE` | SSL mode for DB connection (default: `disable`) |
| `LOG_LEVEL` | Logging level (default: `INFO`) |

### Test

```bash
# Health check
curl http://localhost:8001/

# Create a user (requires admin token)
curl -X POST http://localhost:8001/admin/users \
  -H "X-Admin-API-Key: $ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
```

### Debug

- Logs go to stdout with format `%(asctime)s - admin_api - %(levelname)s - %(message)s`
- Set `LOG_LEVEL=DEBUG` for verbose output
- If `ADMIN_API_TOKEN` is not set, all admin endpoints return 500
- OpenAPI docs at `http://localhost:8001/docs`

## Production Readiness

**Confidence: 62/100**

| Area | Score | Evidence | Gap |
|------|-------|----------|-----|
| User CRUD | 8/10 | Idempotent create (200/201), paginated list, email lookup, JSONB merge on PATCH | JSONB merge is shallow (nested objects overwritten, not deep-merged); `created_at` null repair repeated 9 times |
| Token management | 7/10 | Scoped tokens (user/bot/tx/admin) with prefixed generation; revocation works | Legacy tokens without `vxa_` prefix default to admin scope — verify this is intentional |
| /internal/validate | 3/10 | Correctly resolves token → user_id + scopes for gateway header injection | **CRITICAL: No caller authentication.** Any service (or attacker) can POST to `/internal/validate` with any token and get back user_id, scopes, email. Needs X-Gateway-Key or network-level restriction |
| Analytics queries | 7/10 | Meeting stats, user details, telematics with proper joins to meeting_api.models | Queries may be slow on large tables (no pagination on some analytics endpoints) |
| Webhook endpoint | 7/10 | SSRF validation via `meeting_api.webhook_url.validate_webhook_url()` | Webhook secret stored in plaintext JSONB (not hashed) |
| Meeting-api integration | 9/10 | Dockerfile correctly COPYs and pip-installs meeting-api package; imports work | Tight coupling — if meeting-api package is removed/renamed, build breaks with no fallback |
| Auth middleware | 8/10 | Admin endpoints require X-Admin-API-Key; analytics accepts admin OR analytics token; user endpoints validate X-API-Key with scope check | No rate limiting on any endpoint |
| Tests | 7/10 | test_auth.py (admin/analytics token), test_validate.py (token validation), test_crud.py (all CRUD), test_jsonb_merge.py (JSONB merge) | Tests don't verify /internal/validate lacks caller auth (the critical gap). No integration tests against real DB |
| Docker | 8/10 | Includes admin-models + meeting-api; non-root user (appuser) | No HEALTHCHECK |
| Security | 5/10 | Scope validation correct; SSRF protection on webhooks | /internal/validate unauthenticated; no rate limiting; webhook secret in plaintext; no brute-force protection on token validation |

### Known Limitations

1. **`/internal/validate` is unauthenticated** — hidden from OpenAPI (`include_in_schema=False`) but fully accessible. Any HTTP client can resolve arbitrary API tokens to user identity (user_id, scopes, email). This is the single highest-risk issue across all three components.
2. **Legacy tokens get admin scope** — tokens without the `vxa_` prefix (pre-scoping era) default to `["admin"]` scope. If any legacy tokens exist in the database, they have full admin access.
3. **Webhook secret stored in plaintext** — `webhook_secret` is stored as a plain string in the user's JSONB `data` column. Not hashed, not encrypted at rest (beyond DB-level encryption).
4. **`created_at` null repair pattern** — the same 5-line null check for `created_at` is copy-pasted 9 times throughout main.py. Root cause is SQLAlchemy async `refresh()` not loading server-side defaults. Should be a utility function.
5. **No rate limiting** — token validation, user creation, and analytics endpoints have no rate limiting. Token brute-force is theoretically possible (though token space is large).
6. **Shallow JSONB merge** — `PATCH /admin/users/{id}` with `{"data": {"nested": {"b": 2}}}` will overwrite any existing `nested` object entirely, not merge it.

### Validation Plan (to reach 90+)

- [ ] **P0**: Add caller authentication to `/internal/validate` (X-Gateway-Key header with constant-time comparison)
- [ ] **P0**: Add network-level restriction (Docker network policy) so only api-gateway can reach `/internal/validate`
- [ ] **P1**: Audit legacy tokens in database — revoke or re-issue with explicit scopes
- [ ] **P1**: Add rate limiting on `/internal/validate` (e.g., 100/min per source IP)
- [ ] **P2**: Extract `created_at` null repair into a utility function to reduce duplication
- [ ] **P2**: Hash webhook secrets before storage (or document that plaintext is intentional)
- [ ] **P2**: Add HEALTHCHECK to Dockerfile
- [ ] **P3**: Add integration tests against real PostgreSQL (testcontainers or docker-compose test profile)
- [ ] **P3**: Add pagination to analytics endpoints that currently return unbounded results
