# Auth and Limits

<!-- DESIGN: what we want. Can be ahead of code. Updated before implementation. -->

## Why

Different services handle auth and limits differently. Meeting-api validates tokens and enforces bot limits per user. Agent-api trusts whatever user_id is in the request body with no validation and no container limits. The gateway validates tokens but doesn't enforce resource limits. There's no consistent pattern — each service invented its own approach.

This matters because: a user can spawn unlimited agent containers, bypass auth by hitting agent-api directly on :8100, and there's no way to set or enforce quotas across services.

## Current State

### How each service handles auth today

```
api-gateway :8056
    → validates X-API-Key against admin-api /internal/validate
    → injects X-User-ID, X-User-Scopes headers
    → does NOT enforce any resource limits
    → DOES handle CORS, WebSocket auth

meeting-api :8080
    → get_user_and_token dependency on every endpoint
    → validates token → gets full user object from admin-api
    → reads user.max_concurrent_bots → counts active bots → 403 if over limit
    → 429 from runtime-api if concurrency limit hit
    → mints scoped meeting tokens (transcribe:write)
    → HAS database access (Postgres) for meeting/bot state

agent-api :8100
    → NO token validation
    → reads user_id from request body JSON (trusts it)
    → NO container limits per user
    → NO header validation (X-User-ID ignored)
    → uses Redis for session state, Docker for containers
    → NO database access

admin-api :8057
    → owns users, tokens, scopes
    → /internal/validate endpoint (called by gateway)
    → token scoping: vxa_bot_, vxa_tx_, vxa_user_, vxa_admin_
    → user.max_concurrent_bots field exists
    → CRITICAL: /internal/validate has no caller authentication

telegram-bot :8888
    → calls admin-api get_or_create_auth for token
    → caches token in Redis (24h TTL)
    → uses token as X-API-Key for gateway requests
    → /internal/trigger endpoint has no auth
```

### Token scoping

```
vxa_admin_*   → full access (create users, tokens, manage everything)
vxa_user_*    → user-level (chat, meetings, transcripts)
vxa_bot_*     → bot-level (limited to bot operations)
vxa_tx_*      → transcription-level (read transcripts only)
```

Gateway validates scope prefix. But agent-api doesn't check scopes at all.

### Resource limits

```
meeting-api:
    user.max_concurrent_bots     checked before bot creation     ENFORCED
    runtime-api concurrency      429 if too many containers      ENFORCED

agent-api:
    max containers per user      NONE — unlimited
    max sessions per user        NONE — unlimited
    max workspace storage        NONE — unlimited
    container idle timeout       EXISTS (auto-cleanup)            ENFORCED

gateway:
    rate limiting                NONE
    request size limits          NONE
```

## Open Questions

1. Should agent-api validate tokens itself, or trust gateway headers?
   - If it trusts headers: anyone who can reach :8100 bypasses auth
   - If it validates: it needs to call admin-api (adds latency + dependency)
   - Meeting-api validates itself — should agent-api follow the same pattern?

2. What limits should agent-api enforce?
   - Max containers per user? (like max_concurrent_bots)
   - Max sessions per user?
   - Max workspace size?
   - Where do these limits live? (user record in admin-api? env var? hardcoded?)

3. Should the gateway enforce limits, or leave it to each service?
   - Gateway already validates auth — adding limits there is one place to change
   - But gateway doesn't know service-specific semantics (what's a "bot" vs "container")

4. /internal/validate has no caller auth — any service can call it. Is this a risk?
   - Currently only gateway calls it
   - If agent-api starts calling it, the attack surface grows

5. telegram-bot /internal/trigger has no auth — anyone on the network can trigger messages

6. Agent-api reads user_id from request body. Should it read from X-User-ID header instead?
   - Would align with the gateway injection pattern
   - But breaks direct calls to agent-api (e.g., from telegram-bot)

7. Do we need a unified auth middleware package that all services use?
   - Prevents each service from reimplementing auth differently
   - But adds coupling — every service depends on the auth package

---

<!-- STATE: what we have. Only updated with execution evidence. Never optimistic. -->

## Quality Bar

```
agent-api validates tokens               not implemented     FAIL
agent-api enforces container limits       not implemented     FAIL
gateway enforces rate limits              not implemented     FAIL
/internal/validate has caller auth        not implemented     FAIL
telegram-bot /internal/trigger has auth   not implemented     FAIL
consistent auth pattern across services   no pattern exists   FAIL
```

## Certainty

```
meeting-api auth works                90   get_user_and_token + max_concurrent_bots   2026-03-28
gateway token validation works        90   X-API-Key → admin-api → X-User-ID         2026-03-28
agent-api has no auth                 95   confirmed: no token check, no limits       2026-03-28
/internal/validate is unprotected     90   no caller auth in admin-api code           2026-03-28
token scoping enforced at gateway     80   prefix-based, legacy tokens default admin  2026-03-28
```

## Known Issues

- agent-api trusts request body user_id — no validation
- agent-api has no container limits — DoS risk
- /internal/validate has no caller authentication
- telegram-bot /internal/trigger has no authentication
- Legacy tokens without vxa_ prefix get admin scope by default
- No rate limiting anywhere in the stack
- Token revocation: Redis cache in telegram-bot has no invalidation signal from admin-api
