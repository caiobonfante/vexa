# Mission

Focus: telegram-chat
Problem: token caching has no expiry (revoked tokens cause silent 403s), concurrent users untested, group chat undefined — score capped at 95 by these gaps
Target: token refresh working (revoked token auto-recovers), concurrent users don't cross-talk, score >= 95 with evidence for all checks
Stop-when: target met OR 3 iterations
Constraint: telegram-bot is standalone — no imports from packages/, all API calls through api-gateway, follow manifest.md constraints

## CRITICAL — DO NOT TRUST EXISTING CLAIMS

Previous orchestrator sessions claimed these features exist. They DO NOT. Verify by running:
```bash
grep -n "invalidate_token\|token_refresh\|group_chat\|concurrent\|_handle_group\|mention" services/telegram-bot/bot.py
```
If nothing is found, the code changes were NEVER made. You MUST:
1. Actually edit `services/telegram-bot/bot.py` to add token refresh (TTL + 403 retry)
2. Actually edit `services/telegram-bot/bot.py` to add group chat handling (@mention filtering)
3. Actually add unit tests for these features
4. Commit all changes with `git add` + `git commit`
5. Run the tests to prove they pass

DO NOT just read findings.md and claim the work is done. The code must be MODIFIED.
