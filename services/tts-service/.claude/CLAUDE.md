# TTS Service Testing Agent

## Scope
You test tts-service and ONLY tts-service. Verify it works as described in [README.md](../README.md).

## How to test
Read the README — Why/What/How and Known Limitations are your test specs. Verify each claim.
Integration points: audio synthesis backend. Verify the TTS endpoint works but don't test upstream dependencies.

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
