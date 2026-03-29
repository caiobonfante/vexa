# Auth and Limits

<!-- DESIGN: what we want. Can be ahead of code. Updated before implementation. -->

## Why

Token scoping is half-baked — scope lives only in the token prefix string, not in the database. Can't query tokens by scope, can't revoke by scope, no usage tracking, no expiration. The gateway has no rate limiting. Internal endpoints lack caller authentication.

This matters because: there's no audit trail for token usage, no way to expire tokens, and the gateway is wide open to abuse.

## Design

### Token model (target schema)

```
api_tokens:
    id           INTEGER PK
    token        VARCHAR(255) UNIQUE INDEX
    user_id      INTEGER FK → users.id
    scopes       TEXT[] NOT NULL              ← DB-level scope, source of truth
    name         VARCHAR(255) NULL            ← human label ("CI pipeline", "telegram bot")
    created_at   DATETIME
    last_used_at DATETIME NULL               ← updated on /internal/validate
    expires_at   DATETIME NULL               ← NULL = never expires
```

**Scopes are a Postgres array (`TEXT[]`).** One token can have multiple scopes (e.g. a telegram bot token needs both `bot` and `tx`).

### Valid scopes

```
bot      → meeting bots, webhooks, voice agent
tx       → transcription and meeting data access
browser  → browser sessions (VNC, CDP, workspace)
```

`admin` and `user` scopes removed — both were dead code. Webhooks belong to `bot` scope. Browser sessions have their own scope. Multi-scope tokens (e.g. `bot,tx,browser`) get full access.

### Token creation

Token strings still use `vxa_<scope>_<random>` prefix for human readability, but the DB `scopes` column is the source of truth. Multi-scope tokens use the first scope for the prefix.

```
POST /admin/users/{id}/tokens?scopes=bot,tx&name=telegram-bot
→ token: vxa_bot_<random>, scopes: ['bot', 'tx'], name: "telegram-bot"
```

Invalid or removed scopes (e.g. `admin`, `foo`) return 422.

### Token validation (/internal/validate)

- Reads scopes from DB column, not from prefix parsing
- Updates `last_used_at` on each call
- Rejects expired tokens (where `expires_at` is set and past)
- Requires `INTERNAL_API_SECRET` — not optional, enforced

### Schema evolution

New columns are added to the APIToken model. `ensure_schema()` from `libs/schema-sync/` detects the existing `api_tokens` table lacks these columns and ADDs them on startup. No Alembic — this is an open-source project where we don't know the DB starting state. Schema sync is purely additive, idempotent, and never drops anything. See `features/schema-sync/README.md` for full design.

- `ensure_schema()` adds scopes, name, last_used_at, expires_at columns
- Backfill runs on startup (idempotent):
  - Legacy tokens from main branch (plain random strings, no `vxa_` prefix): scopes = `['bot', 'tx']` (full access)
  - Tokens with removed scopes (`user`, `admin`): migrated to `['bot', 'tx']`
  - Valid prefixed tokens (`vxa_bot_`, `vxa_tx_`): scopes from prefix
- All scope checks use DB column, not token prefix — backward compatible with any token string format
- Zero authentication regressions — all existing tokens continue to work

### Gateway rate limiting

Rate limits enforced at gateway level. Returns 429 when exceeded. Configurable via env var.

### Auth architecture (decisions made)

| Decision | Rationale |
|----------|-----------|
| Meeting-api trusts gateway headers | By design. Reads X-User-ID/X-User-Scopes/X-User-Limits. Does not validate tokens itself. |
| Agent-api stays as-is (no auth) | In dev. Port 8100 must not be externally reachable — network/firewall level, not code. |
| No agent-api container limits | No limits defined yet. Future work. |
| Services are deliberately decoupled | No shared user knowledge between agent-api and meeting-api. Gateway does auth, services do service-specific logic. |
| Telegram /internal/trigger auth skipped | Internal endpoint, low priority. Network-level isolation. |

### How each service handles auth today

```
api-gateway :8056
    → validates X-API-Key against admin-api /internal/validate
    → injects X-User-ID, X-User-Scopes, X-User-Limits headers
    → does NOT enforce resource limits (rate limiting planned)
    → DOES handle CORS, WebSocket auth

meeting-api :8080
    → trusts gateway headers (X-User-ID, X-User-Scopes, X-User-Limits)
    → does NOT validate tokens itself
    → reads max_concurrent from X-User-Limits header → counts active bots → 403 if over
    → 429 from runtime-api if concurrency limit hit

agent-api :8100
    → NO token validation (in dev — must not be externally reachable)
    → reads user_id from request body JSON (trusts it)
    → NO container limits per user
    → NO database access

admin-api :8057
    → owns users, tokens, scopes
    → /internal/validate endpoint (called by gateway)
    → token scopes stored in DB (planned), currently prefix-based
    → user.max_concurrent_bots field exists

telegram-bot :8888
    → calls admin-api get_or_create_auth for token
    → caches token in Redis (24h TTL)
    → uses token as X-API-Key for gateway requests
    → /internal/trigger endpoint has no auth (skipped, low priority)
```

### Resource limits

```
meeting-api:
    user.max_concurrent_bots     checked before bot creation     ENFORCED
    runtime-api concurrency      429 if too many containers      ENFORCED

agent-api:
    max containers per user      NONE — no limits defined yet
    max sessions per user        NONE — no limits defined yet
    max workspace storage        NONE — no limits defined yet
    container idle timeout       EXISTS (auto-cleanup)            ENFORCED

gateway:
    rate limiting                PLANNED — 429 when exceeded
```

---

<!-- STATE: what we have. Only updated with execution evidence. Never optimistic. -->

## Quality Bar

```
api_tokens has scopes column             verified :8066      PASS  2026-03-29
api_tokens has last_used_at, expires_at  verified :8066      PASS  2026-03-29
token creation stores scopes in DB       verified :8066      PASS  2026-03-29
/internal/validate reads DB scopes       verified :8066      PASS  2026-03-29
/internal/validate updates last_used_at  verified :8066      PASS  2026-03-29
/internal/validate rejects expired       verified :8066      PASS  2026-03-29
/internal/validate has caller auth       verified :8066      PASS  2026-03-29
gateway enforces rate limits             verified :8066      PASS  2026-03-29
gateway enforces scope per route         verified :8066      PASS  2026-03-29
legacy tokens backfilled correctly       verified :8066      PASS  2026-03-29
scope=admin returns 422                  verified :8066      PASS  2026-03-29
scope=invalid returns 422 (not 500)      verified :8066      PASS  2026-03-29
```

## Certainty

```
token scopes stored in DB as TEXT[]   99   \d api_tokens shows scopes column, verified         2026-03-29
/internal/validate enforces secret    99   wrong/missing secret → 403, correct → 200           2026-03-29
/internal/validate reads DB scopes    99   response includes scopes from DB column              2026-03-29
/internal/validate rejects expired    99   expired token → 401, verified with 3s TTL token     2026-03-29
last_used_at tracked                  99   NULL→set→updated on consecutive uses                2026-03-29
gateway rate limiting works           99   429 at request #121, resets after window             2026-03-29
gateway scope enforcement works       99   bot→/user/webhook→403, browser→/bots→200             2026-03-29
legacy backfill correct               99   prefixed→parsed, legacy→['bot','tx'], user→['bot','tx'] 2026-03-29
admin scope rejected                  99   scope=admin → 422                                   2026-03-29
meeting-api trusts gateway headers    95   confirmed: reads X-User-ID, no token validation     2026-03-29
agent-api has no auth                 95   confirmed: no token check, port 8100 exposed        2026-03-29
```

## Known Issues (remaining)

- agent-api trusts request body user_id — port 8100 exposed to host despite stated network-only mitigation
- agent-api has no container limits — no limits defined yet
- telegram-bot /internal/trigger has no auth (accepted risk, low priority)
- deploy/compose/docker-compose.yml missing INTERNAL_API_SECRET (agentic stack has it, prod compose does not)
- API key stored in Redis share metadata for transcript sharing — credential exposure risk (P0, out of scope)
- Real secrets committed in .env (Telegram bot token, transcription token) — needs .gitignore + rotation (P0, out of scope)
- MinIO recordings bucket set to public download (P1, out of scope)
- Token cache has 60s TTL — revoked tokens valid briefly (existing, not new)
- Full security audit: features/auth-and-limits/tests/security-audit.md
