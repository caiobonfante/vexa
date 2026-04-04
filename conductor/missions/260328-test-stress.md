# Mission

Focus: conductor
Problem: previous missions had failures — conductor edited code in PLAN, dev slept instead of polling, team coordination was invisible, validator didn't independently verify, state.json got nuked

Target: create a small Python script conductor/test-stress-app.py that:
1. Starts an HTTP server on port 9111
2. Has a /status endpoint that returns {"ready": false} for the first 30 seconds, then {"ready": true}
3. Dev must poll /status (not sleep) until ready=true
4. When ready, write "stress test passed" to conductor/test-stress-output.md
5. Validator must independently curl localhost:9111/status and confirm ready=true AND the output file exists

DoD: conductor/test-stress-output.md exists with "stress test passed", AND localhost:9111/status returns ready=true, verified by validator independently.

Stop-when: DoD met
Constraint: only create/modify files in conductor/. Do not touch any vexa code. Validator must run curl independently — not trust dev's output.
