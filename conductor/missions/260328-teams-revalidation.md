# Mission

Focus: realtime-transcription/ms-teams
Problem: Score claimed 90 but core pipeline (speaker-streams.ts) was rewritten after last test (f50f36cc, Mar 24). No stored test evidence. E2E test scripts have stale DB config (partially fixed: port 5448→5438, db vexa_restore→vexa, container naming updated). Score downgraded to 75 pending re-validation.
Target: Evaluate and fix all issues to restore score to ≥90 with stored evidence. Run E2E tests, fix any pipeline or test harness failures, update findings.md with all post-test commits, store scorer output.
Stop-when: score ≥90 with both E2E tests passing and evidence stored OR 10 iterations
Constraint: Teams meeting already hosted (ID: 9315417349464, passcode: lFVdFnUxxTH2yyQRgw). Auto-admit running in meeting-5-1d5c3adc container. Use tokens from `vexa` DB (not `vexa_restore`).

## Context from re-evaluation

### What changed since last test (2026-03-23)
- **f50f36cc** (Mar 24): 122-line rewrite of speaker-streams.ts — confirmation algorithm changed from per-segment to word-level prefix matching, maxBufferDuration 120s→30s. **HIGH risk.**
- **54df04b4** (Mar 24): Security hardening of segment-publisher.ts + index.ts. LOW risk.
- **5f8dee7d** (Mar 27): Hallucination filter wired into speaker-streams.ts. MEDIUM risk.
- **9e1c774a**: Fix locked speaker name sync in index.ts. IMPROVEMENT.
- **bdd68668**: Streaming VAD, speaker identity, recording.ts timestamp re-alignment. IMPROVEMENT.

### Test script fixes already applied
- Port: 5448→5438 (Postgres host mapping)
- Database: vexa_restore→vexa (admin-api's database)
- Container lookup: `vexa-bot-{id}-*` → DB `bot_container_id` lookup (naming convention changed)
- Tokens in .env updated to vexa DB tokens (Alice/Bob/Charlie TTS bots, user 5 recorder)

### What DELIVER must do
1. Run `features/realtime-transcription/ms-teams/tests/e2e/test-e2e.sh --meeting 9315417349464 --passcode lFVdFnUxxTH2yyQRgw`
2. If it fails on infrastructure (container issues, API errors), fix the test harness and retry
3. Run `features/realtime-transcription/ms-teams/tests/e2e/test-e2e-stress.sh --meeting 9315417349464 --passcode lFVdFnUxxTH2yyQRgw`
4. Copy scorer output to `features/realtime-transcription/ms-teams/tests/e2e/results/` and commit a summary
5. Update `features/realtime-transcription/ms-teams/tests/findings.md` to acknowledge ALL post-test commits
6. Update score in `conductor/state.json` based on actual results

### Infrastructure status (verified 2026-03-28 12:20)
- transcription-service: healthy (CUDA, large-v3-turbo, port 8085)
- api-gateway: healthy (port 8056)
- Redis: healthy (6379)
- Postgres: healthy (5438, databases: vexa + vexa_restore)
- Teams meeting: active with auto-admit
- Bot image: vexa-bot-restore:dev available

### Tokens (from vexa DB, validated)
- Recorder (user 5): vxa_user_1GsamYGP2FVlBuo5hdVNbSFbfqVDR2Zk5RGcehks
- Alice (user 7): vxa_user_AliceTTSbot00000000000000000000000000
- Bob (user 8): vxa_user_BobTTSbot0000000000000000000000000000
- Charlie (user 9): vxa_user_CharlieTTSbot000000000000000000000000

### Diagnosis from iteration 1 (CRITICAL — read this first)

1. **Bot failures: exit 137, self_initiated_leave** — many bots join then immediately leave. Root cause unclear but pattern shows eventually bots DO stay. The latest set (meetings ~124+) is alive with all 6 participants.
2. **Duplicate meeting check** — API returns "active or requested meeting already exists" if you create a bot when one is already active. Clean up first (stop containers + update DB status).
3. **DO NOT sleep for minutes.** Poll every 10-15 seconds: check `docker ps`, check DB status, check bot logs. If a bot fails, diagnose immediately from logs — don't wait and hope.
4. **Caption selectors changed** — Teams now uses `closed-caption-v2-*` selectors (virtual list) instead of the old flat list. The bot code handles this (MutationObserver fires), but caption items show 0. This may be because nobody is speaking yet.
5. **The test script works** — the issue was test harness config (DB port, container naming, tokens), which is already fixed. The script itself is sound.
