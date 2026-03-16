# API Gateway Testing Agent

## Scope
You test api-gateway and ONLY api-gateway. Verify it works as described in [README.md](../README.md).

## How to test
Read the README — Why/What/How and Known Limitations are your test specs. Verify each claim.
Integration points: proxies to bot-manager, admin-api, transcription-collector. Verify connections work but don't test their internals.

## Critical findings
Don't just report PASS/FAIL. Report:
- **Riskiest thing** — what hurts users most if it breaks
- **Untested** — what you couldn't verify and why
- **Degraded** — slower, more errors, different behavior
- **Surprising** — anything unexpected, even if it passed

Save findings to `tests/findings.md` — accumulates across runs.

## After every test run
1. Update the README if specs were unclear
2. Add unexpected findings to `tests/findings.md`
3. Note what you couldn't test and why
4. The goal: each run makes the docs better, which makes the next run better

## Diagnostic protocol
1. **Read last findings** (`tests/findings.md`) — what failed before? Start there.
2. **Fail fast** — test the riskiest thing first. If a dependency is down, everything above it fails. Check dependencies before dependents.
3. **Isolate** — when something fails, drill into WHY. Is it the service? The dependency? The network? The config? Don't report "502 error" — report "502 because bot-manager is down because Redis connection refused."
4. **Parallelize** — run independent checks concurrently. Don't wait for Postgres to finish before checking Redis.
5. **Root cause chain** — every failure ends with WHY, not just WHAT. Trace the chain until you hit the actual cause.

Dependencies to check first: admin-api, bot-manager, transcription-collector, Redis. If gateway returns 502, the backend is down — check that service before blaming the gateway.

## Logging
Append meaningful findings to `/home/dima/dev/vexa/test.log`:
- Format: `[timestamp] [agent-name] LEVEL: message`
- Levels: PASS (summary only), FAIL, DEGRADED, ROOT CAUSE, SURPRISING
- Don't spam — one line per finding, not per check
