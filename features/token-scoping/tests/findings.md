# Token Scoping Test Findings

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Scoped token created | 0 | Not tested | — | POST /admin/tokens with scope, verify token returned |
| In-scope access allowed | 0 | Not tested | — | Use bot-scoped token on bot endpoint, expect 200 |
| Out-of-scope access denied | 0 | Not tested | — | Use bot-scoped token on admin endpoint, expect 403 |
| Token prefix matches scope | 0 | Not tested | — | Verify token string prefix corresponds to scope |
| Legacy token backward compat | 0 | Not tested | — | Use unscoped token, verify full access |
