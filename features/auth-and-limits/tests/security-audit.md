# Security Audit — Auth and Limits Mission

**Date:** 2026-03-29
**Auditor:** Security Officer (automated)
**Scope:** Full codebase audit with focus on auth, token handling, network exposure, secrets

---

## P0 — Critical (fix before shipping)

### 1. API Key Stored in Redis for Transcript Sharing

**File:** `services/api-gateway/main.py:748`
**Risk:** Credential exposure / privilege escalation

The transcript share feature stores the user's raw API key in Redis:
```python
share_metadata = {
    ...
    "api_key": api_key,  # Store API key to fetch fresh transcript
}
await app.state.redis.set(redis_key, json.dumps(share_metadata), ex=ttl)
```

When someone accesses the public share URL, the gateway uses this stored API key to fetch the transcript from the downstream service. Problems:
- Anyone with Redis read access can extract every API key that has been used to create a share link
- The share link effectively acts with the user's full credentials — not just transcript read access
- If Redis is compromised or the share_id is guessable (it's 16 bytes urlsafe — adequate), all shared keys are exposed

**Recommended fix:** Fetch and cache the transcript content at share creation time instead of storing the API key. Or use a service-internal credential (like INTERNAL_API_SECRET) for the refresh fetch, not the user's key.

---

### 2. INTERNAL_API_SECRET Not Configured in Production Docker Compose

**File:** `deploy/compose/docker-compose.yml` (lines 10-20, 44-52)
**Risk:** Unauthenticated internal endpoint access

Neither `api-gateway` nor `admin-api` has `INTERNAL_API_SECRET` in their environment blocks. This means:
- `/internal/validate` accepts calls from any service on the Docker network without authentication
- Any container that gains network access can resolve any API token to its user identity
- The admin-api code handles this with DEV_MODE fallback, but DEV_MODE is not explicitly set either (defaults to false), so currently the endpoint returns 503

**Status:** In-scope — gate G6 addresses this. Dev must add `INTERNAL_API_SECRET` to both services in docker-compose.

---

### 3. Real Secrets Committed to Repository

**File:** `.env` (repository root)
**Risk:** Credential compromise via source code

The `.env` file contains real, active credentials:
```
TELEGRAM_BOT_TOKEN=8573331281:AAEsEa-p4mgMe7bLYG0kcJXkTD6GEneUdCw  ← real Telegram bot token
TRANSCRIPTION_SERVICE_TOKEN=32c59b9f654f1b6e376c6f020d79897d
CLAUDE_CREDENTIALS_PATH=/home/dima/.claude/.credentials.json         ← points to real Claude OAuth creds
ADMIN_API_TOKEN=changeme
```

The `.env` file is not in `.gitignore` (it IS tracked). Anyone with repo access gets these credentials.

**Recommended fix:**
1. Add `.env` to `.gitignore` immediately
2. Rotate the Telegram bot token (`@BotFather` → `/revoke`)
3. Rotate the transcription service token
4. Use `.env.example` with placeholder values only (already exists)
5. Never commit credential file paths

---

### 4. Token Creation Returns 500 for Invalid Scope (instead of 422)

**File:** `services/admin-api/app/main.py:477`
**Risk:** Information disclosure / poor error handling

```python
async def create_token_for_user(user_id: int, scope: str = "user", ...):
    token_value = generate_secure_token(scope=scope)  # raises ValueError for invalid scope
```

`generate_prefixed_token()` raises `ValueError` for invalid scopes, but there's no try/except — FastAPI returns an unhandled 500 with a stack trace.

**Status:** In-scope — listed in mission as a known bug to fix.

---

## P1 — High (fix soon, security-relevant)

### 5. Token Cache Key Collision Risk

**File:** `services/api-gateway/main.py:237`
**Risk:** Authentication bypass via cache poisoning

```python
cache_key = f"gateway:token:{api_key[:16]}"
```

Uses only the first 16 characters of the token for the Redis cache key. Token format is `vxa_<scope>_<random>`:
- `vxa_user_` prefix = 9 chars, leaving only 7 random chars in the cache key
- `vxa_bot_` prefix = 8 chars, leaving 8 random chars
- With enough tokens of the same scope, cache collisions become possible
- A collision means user A's token resolves to user B's identity from cache

**Recommended fix:** Use a hash of the full token: `cache_key = f"gateway:token:{hashlib.sha256(api_key.encode()).hexdigest()[:32]}"`

---

### 6. Agent-API Exposed on Host Network (violates mission constraint)

**File:** `services/agent-api/docker-compose.yml:9`, `.env:66`
**Risk:** Unauthenticated access to agent containers

The mission explicitly states: "Port 8100 must not be externally reachable — network/firewall level, not code." However:
- `services/agent-api/docker-compose.yml` maps `ports: "8100:8100"` to the host
- `.env` has `AGENT_API_URL=http://172.24.0.1:8100` (Docker bridge IP — accessible from host)
- Agent-api has no auth by default (`API_KEY` defaults to empty string)
- `user_id` comes from the request body — any caller can impersonate any user

**Recommended fix:** Use `expose: ["8100"]` instead of `ports` in docker-compose. Access via internal Docker network only.

---

### 7. Agent-API Trusts Client-Supplied user_id

**File:** `services/agent-api/agent_api/main.py:60`
**Risk:** User impersonation

```python
class ChatRequest(BaseModel):
    user_id: str  # ← comes from request body, trusted as-is
```

Combined with no auth (finding #6), any caller can act as any user — creating sessions, reading workspaces, running code in containers.

**Status:** Out of scope per mission ("Agent-api stays as-is"), but the network isolation mitigation (#6) is not actually in place.

---

### 8. Minio Recordings Bucket Set to Public Download

**File:** `deploy/compose/docker-compose.yml:276`
**Risk:** Unauthorized access to meeting recordings

```shell
mc anonymous set download vexa/${MINIO_BUCKET:-vexa-recordings} || true
```

This makes the entire recordings bucket publicly downloadable. If minio's port 9000 is reachable (it's mapped to host at line 248), anyone can download all meeting recordings without authentication.

**Recommended fix:** Remove the `mc anonymous set download` line. Use presigned URLs (already implemented at `/recordings/{id}/media/{id}/download`) for authorized access only.

---

### 9. Docker Socket Access in runtime-api

**File:** `deploy/compose/docker-compose.yml:81`
**Risk:** Container escape / host compromise

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

Grants runtime-api full Docker API access, which is effectively root on the host. This is necessary for the runtime's container management function, but:
- Any code execution vulnerability in runtime-api → full host compromise
- runtime-api is not externally exposed (uses `expose`, not `ports`) — good
- But any compromised service on the Docker network can reach it

**Mitigation:** Document as accepted risk. Consider using Docker's restricted socket proxy (e.g., Tecnativa/docker-socket-proxy) to limit API calls to only what runtime-api needs (container create/start/stop/inspect).

---

### 10. Telegram /internal/trigger Has No Auth

**File:** `services/telegram-bot/bot.py:929`
**Risk:** Unauthorized message injection

```python
@trigger_app.post("/internal/trigger")
async def trigger_chat(request: dict):
    user_id = request.get("user_id")
    message = request.get("message", "Scheduled reminder")
```

No authentication — any service on the network can trigger messages to any Telegram user.

**Status:** Out of scope per mission (accepted risk, network-level isolation). Document and revisit.

---

## P2 — Medium (track and fix)

### 11. No Scope Enforcement at Gateway Route Level

**File:** `services/api-gateway/main.py`
**Risk:** Scope bypass

The gateway injects `X-User-Scopes` into forwarded requests but does not enforce them. A `vxa_bot_` token can access `/user/webhook` (user-only endpoint) because:
1. Gateway validates the token → valid
2. Gateway injects `X-User-Scopes: bot`
3. Gateway forwards to admin-api
4. admin-api's `get_current_user` checks scope against the raw token prefix, not the header

**Status:** In-scope — gate G8 tests for scope enforcement. Dev needs to add scope checking at gateway or service level.

---

### 12. WebSocket Accepts Connection Before Full Auth

**File:** `services/api-gateway/main.py:1735-1746`
**Risk:** Resource exhaustion

```python
await ws.accept()  # Accept first
api_key = ws.headers.get("x-api-key") or ws.query_params.get("api_key")
# "Do not resolve API key to user here"
```

WebSocket is accepted before validating the token. While downstream `/ws/authorize-subscribe` eventually validates, the accepted-but-unauthenticated connection consumes resources.

---

### 13. Weak Default Credentials Throughout

**Files:** `.env`, `deploy/compose/docker-compose.yml`
**Risk:** Default credential attacks

| Credential | Value | File |
|-----------|-------|------|
| ADMIN_API_TOKEN | `changeme` | .env |
| DB_PASSWORD | `postgres` | .env |
| REDIS_PASSWORD | `vexa-redis-dev` | docker-compose.yml |
| JWT_SECRET | `vexa-dev-jwt-secret` | docker-compose.yml |
| MINIO_ACCESS_KEY | `vexa-access-key` | .env |
| MINIO_SECRET_KEY | `vexa-secret-key` | .env |

All predictable defaults. Acceptable for local dev; must be changed for any deployment.

**Recommended fix:** Add a startup check that rejects known-default values when DEV_MODE is false.

---

### 14. Legacy Tokens Bypass All Scope Checks

**File:** `libs/admin-models/admin_models/token_scope.py:57`
**Risk:** Privilege escalation

```python
def check_token_scope(token, allowed_scopes):
    scope = parse_token_scope(token)
    if scope is None:
        return True  # Legacy token — full access
```

**Status:** In-scope — gate G7 addresses this with backfill to `['user', 'bot', 'tx']` scopes in DB.

---

### 15. CORS Wildcard in Agent-API

**File:** `services/agent-api/agent_api/config.py:47`
**Risk:** Cross-origin attacks

```python
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
```

Agent-api defaults to `allow_origins=["*"]` with `allow_methods=["*"]` and `allow_headers=["*"]`. If port 8100 is externally reachable (finding #6), any website can make authenticated requests.

---

## "Honestly Skipped" Mitigation Verification

| Item | Claimed Mitigation | Actual Status |
|------|-------------------|---------------|
| Agent-api no auth | Port 8100 not externally reachable | **FALSE** — port IS exposed to host (finding #6) |
| Agent-api no limits | Future work | OK — documented |
| Telegram /internal/trigger | Network-level isolation | **PARTIAL** — only Docker network isolation, no auth |
| Downstream scope enforcement | Gateway validates, services trust headers | **INCOMPLETE** — gateway doesn't enforce scope per route |

---

## Summary

| Severity | Count | In-scope | Out-of-scope |
|----------|-------|----------|-------------|
| P0 | 4 | 2 (G4, G6) | 2 (API key in Redis, secrets in repo) |
| P1 | 6 | 0 | 6 |
| P2 | 5 | 2 (G7, G8) | 3 |

**Highest priority out-of-scope items:**
1. **Remove API key storage from Redis share metadata** (P0) — credential exposure
2. **Add .env to .gitignore and rotate secrets** (P0) — Telegram token, transcription token
3. **Fix token cache key to use hash** (P1) — authentication bypass risk
4. **Fix agent-api port exposure** (P1) — violates stated constraint
5. **Remove minio public download** (P1) — recording data exposure
