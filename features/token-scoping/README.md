# Token Scoping

## Why

Token scoping is what makes Vexa safe to deploy as a **multi-tenant service**. When you serve multiple users, teams, or customers from one Vexa instance, you need guarantees that a bot-only integration can't access admin endpoints and a read-only dashboard can't spawn bots.

This is the security foundation that separates Vexa from single-user agent tools. OpenClaw explicitly states it's "not a hostile multi-tenant security boundary." Vexa is — token scoping is how.

**Practical examples:**

| Token scope | Who gets it | What they can do | What they can't |
|------------|-------------|-----------------|-----------------|
| `bot` | CI/CD integration, scheduling service | Start/stop bots, read bot status | Manage users, read transcripts |
| `tx` | Dashboard, analytics tools | Read transcripts, search meetings | Start bots, manage users |
| `admin` | Platform operators | Everything | — |
| `user` | End users | User-level operations | Admin operations |

**For SaaS builders:** If you're embedding Vexa into your product for your customers, token scoping ensures each customer's integration token is limited to exactly the operations they need. No accidental cross-tenant access.

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
