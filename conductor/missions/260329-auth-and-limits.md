# Mission: Auth and Limits

Focus: features/auth-and-limits, features/schema-sync
Problem: Token scoping is half-baked — scope lives in the token prefix string, not in the DB. Can't query by scope, can't revoke by scope, no last_used tracking, no expiration. Gateway has no rate limiting. Internal endpoints lack caller auth. And there's no mechanism to safely evolve the DB schema across any starting state (fresh, main-branch, partial).
Target: Schema sync mechanism, proper token model with DB-level scopes, gateway rate limiting, internal endpoint security.
Stop-when: all gates PASS against running services

---

## Decisions Made

1. **`admin` scope removed.** Was dead code — no endpoint differentiated it from `user`. Already deleted from VALID_SCOPES, get_current_user, and tests.
2. **Scope is a Postgres array (`TEXT[]`), not a string.** One token can have multiple scopes (e.g. bot + tx for telegram). Queryable: `WHERE 'bot' = ANY(scopes)`.
3. **Meeting-api trusts gateway headers.** It does NOT validate tokens itself — reads X-User-ID/X-User-Scopes/X-User-Limits from gateway. This is by design.
4. **Agent-api stays as-is.** It's in dev. Port 8100 must not be externally reachable (network-level, not code). Honestly documented, not fixed in this mission.
5. **No agent-api limits.** No limits defined yet. Future work. Honestly documented.
6. **Telegram /internal/trigger auth — skipped.** Internal endpoint, lower priority. Honestly documented.
7. **Services are deliberately decoupled.** No shared user knowledge between agent-api and meeting-api. Gateway does auth, services do service-specific logic.
8. **Schema sync via `ensure_schema()`, not Alembic.** Open-source project — we don't know what state the DB is in. Purely additive, no drops, idempotent. Every service calls it on startup.
9. **No destructive DB operations.** Never drop tables, columns, or data. Orphaned tables (e.g. `transcription_jobs`) left alone.
10. **shared-models is utility-only — no model definitions.** `shared-models/models.py` duplicates every table from admin-models and meeting-api but no service uses it. Strip it down: keep utilities (token_scope, webhook_delivery, storage, scheduler, etc.), remove duplicate model/Base/session definitions. Authoritative sources: `admin-models` for users/tokens, `meeting-api` for meetings/transcriptions/etc.

---

## Part 0: Delete shared-models, redistribute utilities (prerequisite)

`libs/shared-models/` is a zombie package. It duplicates all 8 table models from admin-models and meeting-api with its own Base and database.py. No production service imports its models or database. Its only useful bits are utilities — and those belong in the packages that actually use them.

### What moves where

| Module | Move to | Why |
|--------|---------|-----|
| `token_scope.py` | already in `admin-models` | admin-api owns tokens |
| `webhook_delivery.py` | `meeting-api` | meeting-api sends webhooks |
| `webhook_retry_worker.py` | `meeting-api` | meeting-api retries webhooks |
| `storage.py` | `meeting-api` | meeting-api owns recordings |
| `security_headers.py` | `admin-models` | shared by all services, tiny |
| `schemas.py` | `meeting-api` | meeting/transcription schemas |
| `scheduler.py`, `scheduler_worker.py` | **delete** | runtime-api has its own copy |
| `models.py` | **delete** | duplicate of admin-models + meeting-api |
| `database.py` | **delete** | duplicate, no service uses it |

### After

- `libs/shared-models/` deleted entirely
- Two authoritative packages: `admin-models` (users, tokens), `meeting-api` (meetings, transcriptions, etc.)
- Each service owns its domain, no zombie duplicates
- Update any test imports that reference `shared_models`

---

## Part 1: Schema Sync (foundation)

This must land first — it's the mechanism that makes the token schema change safe across all DB states.

### The problem

We split shared-models into admin-models + meeting-api, each with its own Base. Users upgrading from main lack `segment_id` and `calendar_events`. Fresh users hit FK errors if services start in wrong order. `create_all(checkfirst=True)` won't add new columns to existing tables. No mechanism to converge any DB state to the correct schema.

### The 4 database states

| State | Description | What needs to happen |
|---|---|---|
| Empty | Fresh install | Create all tables in FK order |
| Main-branch | Upgrading from main | Add missing columns/indexes, create new tables. Leave `transcription_jobs` |
| Current branch | Already up to date | No-op |
| Partial | One service started, other didn't | Complete the missing tables without FK errors |

### Solution: `libs/schema-sync/` package

```python
async def ensure_schema(engine, base, prerequisites=None):
    """
    Converge database to match models defined in base.metadata.
    1. If prerequisites given, create those tables first (e.g., admin Base)
    2. create_all(checkfirst=True) for the main base
    3. Inspect existing tables, add any missing columns
    4. Add any missing indexes
    """
```

Integration:
```python
# admin-api startup
await ensure_schema(engine, AdminBase)

# meeting-api startup
await ensure_schema(engine, MeetingBase, prerequisites=AdminBase)
```

---

## Part 2: Token Schema Change

### Current
```
api_tokens:
    id          INTEGER PK
    token       VARCHAR(255) UNIQUE INDEX
    user_id     INTEGER FK → users.id
    created_at  DATETIME
```

### Target
```
api_tokens:
    id           INTEGER PK
    token        VARCHAR(255) UNIQUE INDEX
    user_id      INTEGER FK → users.id
    scopes       TEXT[] NOT NULL              ← NEW: DB-level scope, no more prefix parsing
    name         VARCHAR(255) NULL            ← NEW: human label ("CI pipeline", "telegram bot")
    created_at   DATETIME
    last_used_at DATETIME NULL               ← NEW: updated on /internal/validate
    expires_at   DATETIME NULL               ← NEW: NULL = never expires
```

### How it lands

The new columns are added to the APIToken model. `ensure_schema()` detects the existing `api_tokens` table lacks these columns and ADDs them. No Alembic migration needed — schema sync handles it for any DB state.

### Backward compatibility

Main branch tokens are plain random strings (40 chars, no `vxa_` prefix, no scopes). On upgrade:

1. `ensure_schema()` adds new columns to `api_tokens`
2. Backfill runs on startup (idempotent):
   - Legacy tokens from main (no `vxa_` prefix): scopes = `['bot', 'tx']` (full access)
   - Tokens with removed scopes (`user`, `admin`): migrated to `['bot', 'tx']`
   - Valid prefixed tokens (`vxa_bot_`, `vxa_tx_`): scopes from prefix
3. All scope checks use DB column, not token prefix string
4. `last_used_at` and `expires_at` start as NULL
5. Zero authentication regressions

### Token creation

```
POST /admin/users/{id}/tokens?scopes=bot,tx&name=telegram-bot
→ token: vxa_bot_<random>, scopes: ['bot', 'tx'], name: "telegram-bot"
```

Invalid or removed scopes (e.g. `admin`, `foo`) return 422.

### Token validation (/internal/validate)

- Reads scopes from DB column, not prefix
- Updates `last_used_at` on each call
- Rejects expired tokens (where `expires_at` is set and past)
- Requires `INTERNAL_API_SECRET` — not optional

---

## Part 3: Gateway Rate Limiting

Rate limits enforced at gateway level. Returns 429 when exceeded. Configurable via env var.

---

## Gates

### G0: shared-models deleted, utilities redistributed
```
GATE: libs/shared-models/ does not exist. Utilities live in their owning packages.
TEST:
  - ls libs/shared-models → does not exist
  - grep for "shared_models" imports across all services/ and packages/ → zero hits
  - grep for "class.*Base.*declarative" across libs/ and packages/ → exactly 2 (admin-models, meeting-api)
  - webhook_delivery importable from meeting-api
  - token_scope importable from admin-models
  - All services start and pass health checks
PASS: no zombie package, each domain owns its code
```

### G1: Schema sync works across all DB states
```
GATE: ensure_schema() converges any DB to correct schema
TEST:
  - Empty DB → all tables/columns/indexes created
  - Main-branch DB (has transcription_jobs, lacks segment_id/calendar_events) → columns/tables added, transcription_jobs untouched
  - Current branch DB → no-op, no errors
  - Partial DB (only users table) → completes without FK errors
  - Run ensure_schema twice → idempotent
  - Service startup order doesn't matter
PASS: all 4 states converge, idempotent, no data loss
```

### G2: Token schema columns exist
```
GATE: api_tokens table has scopes, name, last_used_at, expires_at columns
TEST: Connect to Postgres, \d api_tokens, verify columns exist with correct types
PASS: all 4 columns present, added by ensure_schema (not Alembic)
```

### G3: Token creation with scopes
```
GATE: POST /admin/users/{id}/tokens creates tokens with correct DB-level scopes
TEST:
  - Create vxa_user_ token → scopes = ['user'] in DB
  - Create vxa_bot_ token → scopes = ['bot'] in DB
  - Create vxa_tx_ token → scopes = ['tx'] in DB
  - Create token with multiple scopes (bot,tx) → scopes = ['bot','tx'] in DB
  - Create token with name → name stored in DB
  - scope=admin → 422 (removed)
  - scope=invalid → 422 (not 500 — existing bug fix)
PASS: all cases return correct status, DB state matches
```

### G4: Token validation respects DB scopes
```
GATE: /internal/validate reads scopes from DB, updates last_used_at, rejects expired
TEST:
  - Validate a token → response includes scopes from DB column (not parsed from prefix)
  - Validate a token → last_used_at updated in DB
  - Validate an expired token → 401
  - Validate with wrong/missing X-Internal-Secret → 403
PASS: all cases correct
```

### G5: Gateway rate limiting
```
GATE: Gateway enforces request rate limits, returns 429 when exceeded
TEST:
  - Send N+1 requests in rapid succession to gateway
  - First N succeed, remaining get 429
  - Rate limit is configurable (env var or config)
  - Different limits per endpoint group (auth, API, WebSocket) — or global if simpler
PASS: 429 returned when limit exceeded, legitimate traffic unaffected
```

### G6: /internal/validate caller auth enforced
```
GATE: /internal/validate requires INTERNAL_API_SECRET, rejects without it
TEST:
  - Call with correct X-Internal-Secret → 200
  - Call with wrong secret → 403
  - Call with no secret → 403
  - INTERNAL_API_SECRET not set + DEV_MODE=false → 503
PASS: no unauthenticated access to token resolution
```

### G7: Legacy token backfill
```
GATE: Existing tokens in DB have scopes backfilled correctly
TEST:
  - Prefixed tokens: scopes parsed from prefix
  - Legacy tokens (no vxa_ prefix): scopes = ['user', 'bot', 'tx']
  - All tokens still authenticate successfully after migration
PASS: zero authentication regressions
```

### G8: Real enforcement smoke tests (E2E against running services)
```
GATE: Auth, scopes, expiration, and rate limiting are actually enforced end-to-end
TEST (all via gateway :8056, real HTTP calls):

  Token creation:
  - Create user token (scope=user) → 201, token starts with vxa_user_
  - Create bot token (scope=bot) → 201, token starts with vxa_bot_
  - Create tx token (scope=tx) → 201, token starts with vxa_tx_
  - Create multi-scope token (scopes=bot,tx) → 201, DB has both scopes
  - Create token with name → 201, name visible in user details
  - Create token scope=admin → 422 rejected
  - Create token scope=garbage → 422 rejected

  Token authentication through gateway:
  - Use vxa_bot_ token → GET /bots/status → 200 (valid token, gateway lets it through)
  - Use revoked token → GET /bots/status → 401 (gateway rejects)
  - Use garbage string as token → GET /bots/status → 401
  - Use no token at all → GET /bots/status → 401
  - Use expired token → GET /bots/status → 401

  Scope enforcement:
  - Use vxa_user_ token → PUT /user/webhook → 200 (user scope accepted)
  - Use vxa_bot_ token → PUT /user/webhook → 403 (bot scope rejected for user endpoint)
  - Use vxa_tx_ token → PUT /user/webhook → 403 (tx scope rejected for user endpoint)
  - Use vxa_bot_ token → POST /bots → passes auth (bot scope valid for bot ops)
  - Use vxa_tx_ token → GET /transcripts → passes auth (tx scope valid for transcripts)

  Rate limiting:
  - Send 100 rapid requests to gateway → first N succeed, then 429s start
  - Wait for window to reset → requests succeed again
  - Single normal-speed request → always 200 (legitimate traffic unaffected)

  Expiration:
  - Create token with expires_at = 2 seconds from now
  - Use immediately → 200
  - Wait 3 seconds, use again → 401 (expired)

  Last used tracking:
  - Create fresh token → last_used_at is NULL
  - Use token through gateway → query DB → last_used_at is now set
  - Use token again → last_used_at updated to later timestamp

  Legacy token compat:
  - If legacy tokens exist in DB → they still authenticate after migration
  - Their scopes in DB are ['user', 'bot', 'tx']

PASS: every enforcement scenario returns the expected status code. No false positives (blocking legit traffic), no false negatives (letting bad tokens through).
```

### G9: Dashboard shows new token fields and Playwright E2E
```
GATE: Dashboard profile page displays scopes, name, last_used_at, expires_at for tokens. Playwright tests verify via remote browser session.
TEST:
  - Profile page loads, shows API keys with scope badges (bot/tx/user)
  - "last used" column shows relative time or "Never"
  - "expires" column shows date or "Never"
  - Token name displayed (not just "API Key")
  - Create key dialog works: name + scope selection → key created with correct scope badge
  - Key list refreshes after creation
  - Revoke key works → key disappears from list
  - All verified via Playwright against dashboard running through remote browser CDP
PASS: all UI elements render correctly, create/revoke flows work
```

---

## Honestly Skipped

| Item | Why | Mitigation |
|------|-----|------------|
| Agent-api token validation | In dev, not externally facing | Port 8100 must not be externally reachable — network/firewall level |
| Agent-api container limits | No limits defined yet | Future work when limits are defined on user model |
| Telegram /internal/trigger auth | Internal endpoint, low traffic | Network-level isolation, same as agent-api |
| Downstream scope enforcement | Services don't check X-User-Scopes | Gateway validates, services trust headers — by design for now |

---

## Files

| File | Role |
|------|------|
| `libs/shared-models/` | DELETE entirely — redistribute utilities to admin-models and meeting-api |
| `libs/schema-sync/` | NEW: ensure_schema() package — foundation for all schema changes |
| `libs/admin-models/admin_models/models.py` | APIToken model — add scopes, name, last_used_at, expires_at |
| `libs/admin-models/admin_models/database.py` | Call ensure_schema() from init_db() |
| `libs/admin-models/admin_models/token_scope.py` | Scope parsing — already updated (admin removed) |
| `services/meeting-api/meeting_api/database.py` | Call ensure_schema() from init_db() |
| `services/admin-api/app/main.py` | Token creation, /internal/validate — use DB scopes |
| `services/api-gateway/main.py` | Rate limiting middleware |
| `features/auth-and-limits/README.md` | Feature README — update after validation |
| `features/auth-and-limits/tests/` | E2E tests for auth gates |
| `features/schema-sync/README.md` | Feature README — update after validation |
| `features/schema-sync/tests/` | E2E tests for schema convergence |
| `services/dashboard/src/app/profile/page.tsx` | Profile page — show new token fields |
| `services/dashboard/src/app/api/profile/keys/route.ts` | API route — pass scopes/name, return new fields |
| `features/auth-and-limits/tests/dashboard.spec.ts` | Playwright E2E tests for dashboard token UI |
| `.claude/commands/test-dashboard-auth.md` | Command to run dashboard Playwright tests via remote browser |
