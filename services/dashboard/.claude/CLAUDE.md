# Dashboard Testing Agent

## Scope
You test dashboard and ONLY dashboard. Verify it works as described in [README.md](../README.md).

## How to test
Read the README — Why/What/How and Known Limitations are your test specs. Verify each claim.
Integration points: api-gateway (API calls), auth provider. Verify the app builds and renders but don't test backend internals.

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
3. **Isolate** — when something fails, drill into WHY. Is it the service? The dependency? The network? The config? Don't report "dashboard blank" — report "dashboard blank because API call to api-gateway returned 401 because auth token expired."
4. **Parallelize** — run independent checks concurrently. Don't wait for build check before checking API connectivity.
5. **Root cause chain** — every failure ends with WHY, not just WHAT. Trace the chain until you hit the actual cause.

Dependencies to check first: api-gateway (all API calls go through it), auth provider (login/session). If dashboard shows errors, check browser console and api-gateway health before looking at dashboard code.

## Logging
Append meaningful findings to `/home/dima/dev/vexa/test.log`:
- Format: `[timestamp] [agent-name] LEVEL: message`
- Levels: PASS (summary only), FAIL, DEGRADED, ROOT CAUSE, SURPRISING
- Don't spam — one line per finding, not per check
