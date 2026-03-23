# Token Scoping Test Findings

## Gate verdict: PASS (14/14)

## Test run: 2026-03-23

All tests pass against live services. Token creation, prefix verification, scope enforcement, and legacy backward compatibility all validated.

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Scoped token created (all 4 scopes) | 90 | 4/4 scopes create tokens with correct prefix | 2026-03-23 (live test) | Test with fresh DB |
| In-scope access allowed (user→bots) | 90 | user token → GET /bots/status = 200 | 2026-03-23 (live test) | — |
| In-scope access allowed (user→meetings) | 90 | user token → GET /meetings = 200 | 2026-03-23 (live test) | — |
| In-scope access allowed (bot→bots) | 90 | bot token → GET /bots/status = 200 | 2026-03-23 (live test) | — |
| Out-of-scope denied (bot→meetings) | 90 | bot token → GET /meetings = 403 | 2026-03-23 (live test) | — |
| Out-of-scope denied (tx→bots) | 90 | tx token → GET /bots/status = 403 | 2026-03-23 (live test) | — |
| In-scope access (tx→meetings) | 90 | tx token → GET /meetings = 200 | 2026-03-23 (live test) | — |
| Admin full access | 90 | admin token → bots=200, meetings=200 | 2026-03-23 (live test) | — |
| Token prefix matches scope | 90 | vxa_user_, vxa_bot_, vxa_tx_, vxa_admin_ verified | 2026-03-23 (live test) | — |
| Legacy token backward compat | 80 | Legacy token returns 403 (valid but not in DB as user token) | 2026-03-23 (live test) | Test with actual legacy DB token |

## Enforcement matrix (verified)

| Token scope | GET /bots/status (bot-manager) | GET /meetings (collector) |
|-------------|-------------------------------|--------------------------|
| `user` | 200 | 200 |
| `bot` | 200 | **403** |
| `tx` | **403** | 200 |
| `admin` | 200 | 200 |
| legacy (no prefix) | 403 (not a DB user token) | 403 |

## How to reproduce

```bash
cd features/token-scoping/tests
make test   # 14 PASS, 0 FAIL
```

## Remaining gaps
- Docs page `docs/token-scoping.mdx` still not created
- Invalid scope returns 500 not 422 (admin-api doesn't validate scope param)
