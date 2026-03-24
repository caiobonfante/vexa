# Token Scoping

> **Confidence: 90** — 14/14 tests pass. All 4 scopes (`user`, `bot`, `tx`, `admin`) enforced at gateway. Legacy unscoped tokens backward-compatible.
> **Tested:** Token creation with scope, prefix visibility, gateway enforcement (in-scope → 200, out-of-scope → 403), legacy token compatibility.
> **Not tested:** Per-endpoint granularity (currently per-service), per-meeting RBAC.
> **Contributions welcome:** Per-meeting RBAC ([#158](https://github.com/Vexa-ai/vexa/issues/158)), analytics token scope ([#160](https://github.com/Vexa-ai/vexa/issues/160)), finer-grained per-endpoint scoping.

## Why

Least-privilege API tokens for multi-tenant deployments. A bot-only token can't manage users; a read-only token can't start bots. Required for safe multi-user deployments where different integrations need different access levels.

**Scopes:** `bot` (bot operations), `tx` (transcripts), `admin` (everything), `user` (user-level). Enforced at gateway. Legacy unscoped tokens get full access for backward compatibility.

## What

This feature creates API tokens with specific permission scopes and enforces those scopes at the gateway level.

### Documentation
- [Token Scoping](../../docs/token-scoping.mdx)

### Components

- **shared-models**: defines the token model, scope enum, and token prefixes
- **admin-api**: creates scoped tokens (POST /admin/users/{user_id}/tokens?scope=...)
- **api-gateway**: reads token scope and enforces access control per endpoint

### Data flow

```
admin-api (create token with scope) → Postgres (store token + scope)
api-gateway (read token scope) → allow/deny request
```

### Key behaviors

- Tokens have a scope field (e.g., user, bot, tx, admin)
- Token prefixes indicate scope (visible in the token string)
- api-gateway checks scope before proxying to backend
- Out-of-scope requests return 403
- Unscoped (legacy) tokens have full access for backward compatibility

### Data stages

| Stage | Contents | Produced by | Consumed by |
|-------|----------|-------------|-------------|
| **raw** | Token creation requests + scope definitions | admin-api | Postgres |
| **rendered** | Access control results (200/403 per endpoint per scope) | api-gateway | Test assertions |

No collected datasets yet. This feature is deterministic — capture scope×endpoint matrix results for regression testing.

## How

This is a cross-service feature. Testing requires admin-api and api-gateway running.

### Verify

1. Start the compose stack: `make all` (from `deploy/compose/`)
2. Create a scoped token: `POST /admin/users/{user_id}/tokens?scope=bot`
3. Use the token for `GET /bots/status` — should succeed (200)
4. Use the token for `GET /admin/users` — should fail (403)

### Known limitations

- Scope granularity is coarse (per-service, not per-endpoint)
- Legacy tokens without scope get full access
