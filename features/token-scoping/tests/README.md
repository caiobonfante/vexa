# Token Scoping Tests

## Testing approach

Token scoping is a **deterministic, request/response** feature — no meetings, no audio, no TTS. Tests hit the admin-api (create tokens) and api-gateway (enforce scopes) with curl.

### Test types

| Test | What it validates | Needs |
|------|------------------|-------|
| `make smoke` | Create one scoped token, verify prefix | admin-api |
| `make test-create` | Create tokens for all 4 scopes, verify prefixes | admin-api |
| `make test-enforce` | Use scoped tokens against endpoints, check 200/403 | admin-api + api-gateway |
| `make test-legacy` | Legacy unscoped tokens retain full access | api-gateway |

### Scopes

| Scope | Prefix | Intended access |
|-------|--------|----------------|
| `user` | `vxa_user_` | Standard user endpoints (bots, meetings, transcripts) |
| `bot` | `vxa_bot_` | Bot operations only |
| `tx` | `vxa_tx_` | Transcription read-only |
| `admin` | `vxa_admin_` | Admin operations |

### How to run

```bash
cd features/token-scoping/tests

# Setup
cp ../.env.example ../.env  # fill in values

# Run
make smoke           # quick check
make test            # all tests
make test-enforce    # just enforcement
make clean           # revoke test tokens
```

### What to look for

- PASS: scoped tokens have correct prefix (`vxa_{scope}_`)
- PASS: in-scope requests return 200
- PASS: out-of-scope requests return 403
- PASS: legacy tokens (no prefix) still work

### Known issues

- Invalid scope returns 500 instead of 422 (admin-api doesn't validate scope param)
- Scope enforcement is not in api-gateway — it delegates to admin-api/bot-manager
