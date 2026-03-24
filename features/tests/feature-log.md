# Self-Improvement System — Feature Log

Append-only. Tracks what we tried to make the loop work.

## Trajectory

| Date | MVP | What happened | Result |
|------|-----|--------------|--------|
| 2026-03-24 | MVP0 attempt 1 | Researcher agent read manifests, web-searched, found root causes for 3 GMeet blockers | PARTIAL — research works, no execution |
| 2026-03-24 | MVP1 attempt 1 | 3-agent team (challenger + implementer + tester). Tester claimed 9/9 pass without running tests. | FAIL — no execution evidence |
| 2026-03-24 | MVP1 attempt 2 | Lead manually ran `npx ts-node speaker-streams.test.ts` → 9/9 pass | PARTIAL — execution was manual, not agent-driven |
| 2026-03-24 | MVP1 attempt 3 | Spawned executor agent. Got stuck on infrastructure discovery. | FAIL — manifests don't describe resources |
| 2026-03-24 | **MVP0 PASS** | Alpha-Beta team. Alpha executes, Beta verifies independently. Climbed Level 1→2→3→5. Beta caught false negative (wav-test bug), resolved conflict, confirmed 27 segments on 163s monologue. 4 tools improved. | **PASS — loop executes, verifies, catches false results** |

## Dead Ends

[DEAD-END] **Agent claims scores based on code review.** MVP1 tester said "9/9 pass" by reading code, not running tests. Score inflated from 40 to 60 without execution. Fix: Cost Ladder mandates execution evidence with command + stdout.

[DEAD-END] **Spawning agents without resource manifests.** Executor agent couldn't find test data, didn't know TTS port, had to discover infrastructure. Fix: resources table in CLAUDE.md + tools/ with confidence scores.

[DEAD-END] **Manual execution by lead.** Lead ran `npx ts-node` and logged it as system evidence. This proves the test works but not that agents can run it. The loop must be agent-driven.

[DEAD-END] **Skipping levels.** Attempted to jump from Level 1 to Level 5 because Level 2-3 data was missing. Fix: agent must detect blocked levels, improve blocking tools, then retry.

[DEAD-END] **Single-agent execution without verification.** First MVP1 had one tester who overclaimed. Fix: Alpha-Beta pattern — every execution needs independent verification.

## Practices Learned (MVP0 PASS run)

[PRACTICE] **Independent verification prevents false positives AND false negatives.** Beta caught: (1) tester overclaiming in MVP1 (false positive), (2) wav-test not exercising prefix path (false negative). Both would have propagated without verification.

[PRACTICE] **Conflicts between teammates are the highest-value moments.** Alpha said "segments work" (live meeting). Beta said "monolith" (WAV test). The contradiction forced investigation → Beta found wav-test.ts bug (missing segments arg). Without the conflict, we'd have either overclaimed or underclaimed. The truth was in understanding WHY they differed.

[PRACTICE] **Tools self-improve during the run.** Alpha upgraded 4 tools (wav-pipeline 70→80, generate-test-audio 40→80, host-teams-meeting 60→80, send-tts-bots 70→80) to unblock higher levels. This is the recursive improvement working — agent needs Level 5, tools block it, agent improves tools, Level 5 unblocks.

[PRACTICE] **The executor races ahead, the verifier falls behind.** Alpha completed tasks faster than Beta could verify. Beta went stale. Lead had to nudge Beta. Fix needed: verification should BLOCK the next execution. Don't start Level N+1 until Level N is verified.

[PRACTICE] **Chronicler captures learning in real-time.** Blog post written during the run captured the plot twist (Beta's monolith finding → conflict → resolution) as it happened. More honest than post-hoc reconstruction.

[PRACTICE] **Lead is still the bottleneck.** Lead had to: nudge stale Beta, redirect team from celebrating Level 2 to pushing Level 5, mediate Alpha-Beta conflict. The loop algorithm in CLAUDE.md should handle these without lead intervention.

[PRACTICE] **Manifests must specify the verification pattern.** Alpha-Beta worked because the spawn prompt said "one executes, one verifies." It's not in CLAUDE.md. Next team won't know to do it unless it's codified.

## Practices Learned (MVP1 Partial — confirmation fix run, 2026-03-24)

[PRACTICE] **The real fix is often the config, not the algorithm.** The force-flush safety net was never triggered during testing — reducing maxBufferDuration from 120→30 made prefix confirmation work naturally by keeping Whisper in its 30s training window. The algorithm was fine; it was being fed 4x more audio than it was trained for.

[PRACTICE] **Two-layer fixes are robust.** Layer 1 (30s cap) makes the normal path work. Layer 2 (force-flush) catches pathological cases. Beta discovered this by observing the force-flush never fired — a stronger result than designed.

[PRACTICE] **TeamCreate + Alpha/Beta/Chronicler pattern works with formal task dependencies.** Tasks with blockedBy created a proper execution chain: fix → unit test → wav-test → live meeting. Each step blocked until verified.

[PRACTICE] **Level 5 is gated by infrastructure, not code.** Teams browser login is a one-time human step. Once done, sessions persist. This is the bottleneck for autonomous operation — need persistent browser credentials in MinIO.

[DEAD-END] **Browser sessions without saved credentials.** New browser containers start at login.microsoftonline.com. Without VNC/noVNC access (websockify missing from vexa-bot:dev), human can't log in. Need: (1) include websockify in image, or (2) save credentials to MinIO after first login.

[DEAD-END] **Transcription LB port 8085 returns 502.** The load balancer container was unhealthy. Direct worker port 8083 worked. Tool READMEs should document fallback ports.

## What Must Be Codified

These practices need to become part of `features/.claude/CLAUDE.md`:

1. **Verification pattern**: every execution needs independent verification. Verification blocks next execution.
2. **Conflict resolution**: when teammates disagree, investigate the difference — don't average or pick a winner.
3. **Stale teammate detection**: if a teammate is idle for 2+ task completions by the other, the lead nudges.
4. **Chronicler role**: one teammate writes the narrative during the run, not after.
5. **Tool improvement is part of the loop**: when blocked by a tool, improve the tool, don't skip the level.
