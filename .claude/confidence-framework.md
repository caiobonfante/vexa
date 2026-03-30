# Confidence Framework

A living paper on how agents in this project track, calibrate, and act on confidence. Updated as we learn.

## Core Principles

1. **Confidence is computed from evidence, never self-reported.** LLMs are 5.5x more likely to be confidently wrong than unsure about something right (Kaddour et al., 2026). Self-reported "I'm 85% confident" is nearly meaningless.

2. **Gotcha memory is the most important memory.** Every mistake, false blocker, and surprise gets recorded with root cause, mitigation, and decay. This is what makes the system smarter over time.

3. **Don't stop until high confidence OR hard blocker.** But confidence alone is never sufficient — it must be paired with observable verification (test pass, curl 200, visible in browser).

4. **Calibrate after every delivery.** When the human reveals the agent was wrong despite high confidence, find the root gap, discuss it, and remember it. Same for false blockers.

## The Confidence Model

### Bayesian Updating with Sigmoid Output

We use log-odds Bayesian updating, not exponential decay. Exponential decay can only grow and grows fastest at step 0 (when the agent knows least). Bayesian updating handles both positive and negative evidence naturally.

```
                    100 ─┐
                         │          ╭───────── asymptote (can't reach 100)
                    85 ──│─────────╯
                         │       ╱
                    70 ──│─────╱── positive evidence accumulates
                         │   ╱
                    50 ──│──╳────── starting point (maximum uncertainty)
                         │   ╲
                    30 ──│─────╲── negative evidence drops it
                         │       ╲
                    15 ──│─────────╲
                         │          ╰───────── floor (can't reach 0)
                     0 ──┘
                         step 0    step N
```

**Math:**
```
log_odds starts at 0 (maps to 50%)

On positive evidence (test pass, successful verification):
    log_odds += evidence_strength    (0.1 weak ... 1.0 strong)

On negative evidence (error, test fail, gotcha triggered):
    log_odds -= evidence_strength

Clamped to [-4.0, +4.0] (maps to ~2% - ~98%)

confidence = sigmoid(log_odds) = 1 / (1 + exp(-log_odds))
confidence_100 = int(confidence * 100)
```

**Evidence strength examples:**
| Signal | Strength | Direction |
|--------|----------|-----------|
| Test suite passes | 1.0 | + |
| curl returns expected response | 0.7 | + |
| Code compiles/lints clean | 0.3 | + |
| Agent "reviewed code, looks correct" | 0.0 | ignored |
| Test fails | 1.0 | - |
| Error in logs | 0.5 | - |
| Gotcha pattern matched | gotcha.severity | - |
| Retry needed | 0.3 | - |
| Previous delivery of similar task was wrong | 0.8 | - |

Key: **observable signals only.** Agent saying "I think this is right" scores 0.0.

## Stopping Criteria

```
for each step:
    update_confidence(step_evidence)

    if confidence >= 85 AND adversarial_check_passed AND verification_passed:
        DELIVER

    elif confidence >= 70 AND verification_passed AND no_open_gotchas:
        DELIVER with note "moderate confidence — recommend human verification of: [gaps]"

    elif hard_blocker AND blocker_verified:
        STOP with blocker report

    elif budget_exhausted:
        DELIVER best effort with honest confidence report

    elif confidence_stagnant(5 steps):
        ESCALATE — agent is spinning, not making progress

    elif confidence_oscillating(amplitude > 15, period < 4):
        ESCALATE — contradictory evidence, needs human judgment

    else:
        CONTINUE
```

**Stagnation detection:** If confidence hasn't moved more than 2 points in either direction for 5 consecutive steps, the agent is spinning. It should escalate or change approach, not loop forever.

**Oscillation detection:** If confidence swings >15 points in both directions within 4 steps, there's contradictory evidence. Escalate to human rather than continuing.

**Critical rule:** Never stop on confidence alone. The stop hook already enforces verification. Confidence augments the stop hook — it doesn't replace it.

## Adversarial Self-Assessment

When confidence crosses 80%, the agent must run an adversarial check before declaring completion:

**Ask:** "What bugs can you find in what you just did?"
**Don't ask:** "Is this correct?" (triggers confirmation bias)

This reframing reduced overconfidence by ~15 percentage points in research (Kaddour et al., 2026). The agent actively looks for problems instead of confirming its work.

The adversarial check can lower confidence (if bugs found) or confirm it (if no bugs found after genuine effort). Either outcome is useful.

## Gotcha Memory

Gotchas are the most important persistent memory. They encode what the system has learned from mistakes, surprises, and false blockers.

### Structure

```yaml
gotcha:
  pattern: "what situation triggers this"
  root_cause: "why it's a problem"
  mitigation: "what to do instead"
  severity: 0.0-1.0 (how much to lower confidence when matched)
  confirmation_count: N (times this gotcha was confirmed)
  false_positive_count: N (times it fired but the fear didn't materialize)
  last_triggered: date
  source: "delivery failure / false blocker / human feedback / observation"
```

### Decay Is Natural, Not Maintained

No separate decay system. Gotchas are memory files with dates and confirmation counts. When an agent reads a gotcha and sees "confirmed once 2 months ago, false-positived twice since" — it naturally weights it low. A gotcha confirmed yesterday 5 times carries itself.

Agents update or remove gotchas through normal memory maintenance:
- Gotcha confirmed again → update `times_confirmed`, `last_confirmed`
- Gotcha proved wrong → update `times_false_positive`, or remove if clearly invalid
- Accumulating too many weak gotchas → prune the obviously stale ones

The risk to watch for: **learned helplessness** — too many gotchas making the agent overly cautious. If an agent can't reach high confidence because gotchas keep firing, that's a signal to prune.

### Where Gotchas Live

Gotchas are stored in the agent's memory system (`.claude/agent-memory/` or feature `tests/findings.md`) depending on scope:
- **Project-wide gotchas** (e.g., "docker compose up takes 30s, don't declare failure before that"): agent memory
- **Feature-specific gotchas** (e.g., "PulseAudio needs 500ms between unmute and audio start"): feature findings.md

### Gotcha Sources

Gotchas are created from four events:

1. **Delivery failure with high confidence.** Agent delivered at confidence 85+, human found it wrong. Root cause analysis produces a gotcha.

2. **False blocker.** Agent declared a hard blocker that turned out not to be one. Pattern: "false blocker: [description]".

3. **Human feedback.** Human tells the agent something that contradicts its model. Don't store the surface correction — discuss with the human to extract the root gap. Why was the agent's model wrong? What assumption failed? Store the root cause, not the symptom.

4. **Observation during work.** Agent notices something surprising (unexpected latency, API returning different format than docs, etc.). Store proactively.

## Post-Delivery Calibration

The calibration loop that makes the whole system better over time.

### When Agent Was Confident But Wrong

1. **Find the root gap.** What evidence was missing? What evidence was misleading? Was the verification insufficient?
2. **Classify the failure:**
   - Missing verification: "I didn't test X" → add X to the verification checklist
   - Misleading evidence: "Test passed but tested the wrong thing" → gotcha about test coverage gaps
   - Overconfident self-assessment: "I said 'looks correct' without running it" → reinforce: observable evidence only
   - Environment mismatch: "Worked in test, failed in prod" → gotcha about environment differences
3. **Discuss with human.** The root cause may be non-obvious. The human may see patterns the agent misses.
4. **Store as gotcha** with high initial severity (0.8+).

### When Agent Flagged a False Blocker

1. **Find why the agent thought it was a blocker.** Was the error message misleading? Did the agent not try hard enough? Was it a transient failure?
2. **Classify:**
   - Transient failure: "API was down for 30 seconds" → gotcha: "retry before declaring blocker"
   - Agent gave up too early: "tried one approach, declared blocked" → gotcha: "try N approaches before blocking"
   - Hallucinated problem: "agent said X doesn't support Y, but it does" → gotcha: "verify claims about capability before blocking"
3. **Discuss with human.**
4. **Store as gotcha.**

### Tracking Calibration Over Time

After every human verdict (accept/reject):
```
record: (predicted_confidence, actual_outcome)
```

Over a rolling window, compute how well-calibrated the system is. If consistently overconfident (e.g., 80% confidence but only 50% success), apply a scaling factor to future confidence scores.

This is the evaluator agent's role expanded — not just checking individual deliveries, but tracking the pattern.

## Known Gotchas

### G1: Test the system, not just the feature

**Pattern:** Agent runs feature-specific tests (Playwright, curl), they pass, confidence rises. But the system itself (nginx, docker, dashboard reachability) is broken — sometimes by the agent's own testing.

**Root cause:** Narrow test scope. Agent verifies "does my change work?" without checking "is the thing the user actually touches still working?"

**Mitigation:** Before reporting confidence above 70, verify the basic user entry point works: can you load the dashboard URL? Does the API gateway respond? Is the service the user interacts with healthy?

**Source:** 2026-03-29, session "2903". 8/8 Playwright tests passed, agent claimed 80/100, dashboard was unreachable because agent's curl bombardment killed nginx.

---

### G3: Flailing — patching without root cause

**Pattern:** After a failed delivery, agent starts trying fixes: restart service, add config, kill process, restart again. Each attempt is a guess. Confidence not tracked. No diagnosis step.

**Root cause:** Agent defaults to "try things until it works" under pressure. No protocol for "stop, diagnose, understand before touching anything."

**Mitigation:** When delivery fails, the protocol is:
1. Stop. Don't touch code or services.
2. Read logs/errors. Form a hypothesis about the root cause.
3. Report current confidence and what evidence would raise it.
4. If confidence isn't rising after 3 diagnostic steps, escalate.
5. Only then attempt a fix — one fix per hypothesis, verify after each.

**Source:** 2026-03-29, session "2903". Dashboard didn't load after VNC rewrite delivery. Agent tried allowedDevOrigins, process restart, cookie analysis, another restart — none based on diagnosis.

---

### G2: CLAUDE.md changes don't propagate to running sessions

**Pattern:** Framework rules added to CLAUDE.md mid-session are not picked up by already-running Claude Code sessions.

**Root cause:** CLAUDE.md is loaded at session start, not live-reloaded.

**Mitigation:** After updating CLAUDE.md with new rules, existing sessions must be restarted to pick them up.

**Source:** 2026-03-29. Confidence framework added to conductor/CLAUDE.md, but running session "2903" didn't apply it.

---

### G4: Instructions alone don't change behavior

**Pattern:** Confidence protocol written in CLAUDE.md. Agent restarts, loads it. Human says "fail." Agent ignores the protocol entirely — no confidence report, no gotcha check, no diagnosis step. Goes straight to trying fixes.

**Root cause:** LLMs treat prompt instructions as suggestions. Under task pressure, they default to their trained behavior (investigate → fix) and skip protocol steps that feel like overhead.

**Mitigation:** Mechanical enforcement, not prompt instructions. Options:
1. **Hook-based:** A pre-tool hook that blocks Bash/Edit calls unless the agent has reported confidence in the last N messages
2. **Evaluator-based:** Evaluator rejects deliveries that don't show confidence tracking in the conversation
3. **Template-based:** Force agent output through a structured template that requires confidence fields

The stop hook works because the agent can't bypass it. Confidence needs the same — a mechanism the agent can't skip.

**Source:** 2026-03-29. Agent restarted with .claude/CLAUDE.md containing full confidence protocol. On "fail" from human, protocol was completely ignored.

**Status:** Resolved — Stop hook mechanically enforces confidence reporting. First successful block on 2026-03-29.

---

### G6: Hook settings format requires nested `hooks` array

**Pattern:** Hooks configured as `{"type":"command","command":"..."}` directly in the Stop array. Claude Code silently ignores them — no error, no `/hooks` listing.

**Root cause:** The schema requires `{"hooks":[{"type":"command","command":"..."}]}` nesting. Wrong format passes JSON validation but fails schema validation silently.

**Mitigation:** Always use the nested format. Hardcode absolute paths — no `$(...)` shell expansion in settings JSON.

**Source:** 2026-03-29. Hooks didn't appear in `/hooks` for multiple sessions. Schema error only surfaced when attempting to edit `~/.claude/settings.json`.

---

### G5: Relative paths in hooks break from subdirectories

**Pattern:** Hook command uses relative path (`conductor/hooks/confidence-check.sh`). Session started from `conductor/` subdirectory. Path resolves to `conductor/conductor/hooks/...` — doesn't exist. Hook silently fails.

**Root cause:** Settings are at repo root but sessions can start from any subdirectory.

**Mitigation:** Use `$(git rev-parse --show-toplevel)/path/to/hook.sh` in hook commands. Shell expansion resolves the absolute path regardless of cwd.

**Source:** 2026-03-29. Stop hook configured but never fired — path didn't resolve from conductor/ directory.

---

## Integration with Existing System

### Stop Hook (unchanged)

The stop hook remains the mechanical enforcement. It checks binary conditions: does the evidence exist? does the test pass? Confidence doesn't replace the stop hook — it augments the agent's decision about when to attempt stopping.

### Evaluator Agent (expanded)

The evaluator already checks for inflated scores and missing evidence. New responsibilities:
- Check that confidence score matches evidence strength (not self-reported)
- Verify adversarial self-assessment was performed at high confidence
- Track calibration: did past high-confidence deliveries hold up?
- Flag patterns: "agent has been overconfident on this type of task 3 times in a row"

### Findings.md (expanded)

Add a confidence column to the certainty table:
```
| Check | Score | Confidence | Evidence | Last checked |
|-------|-------|------------|----------|--------------|
| Bot joins meeting | 85 | 82 (Bayesian) | curl returned 200, bot visible in VNC | 2026-03-29 |
```

Score = human-assigned quality. Confidence = agent-computed belief that the score is accurate.

## Layered Rollout

Don't implement everything at once. Each layer adds value independently.

| Layer | What | Mechanism | Status |
|-------|------|-----------|--------|
| 0 | Stop hook with binary checks | check-completion.py | Done |
| 1 | Evidence-based confidence in findings.md | Count observable signals, compute score | Next |
| 2 | Gotcha memory with decay | Agent memory files, severity tracking | After L1 |
| 3 | Post-delivery calibration loop | Record predictions vs outcomes, adjust | After L2 |
| 4 | Adversarial self-assessment at high confidence | "What bugs can you find?" prompt | After L3 |

## Research References

Full research report: `features/agentic-runtime/tests/confidence-calibration-research.md`

### Core Papers

| Paper | Finding | Link |
|-------|---------|------|
| Agentic Uncertainty (Kaddour et al., Feb 2026) | Agents 5.5x more likely to be confidently wrong; adversarial framing reduces overconfidence 15pp | [arxiv 2602.06948](https://arxiv.org/abs/2602.06948) |
| Holistic Trajectory Calibration (Zhang et al., Jan 2026) | 48-dim features from agent trajectories predict success; works with 400 samples | [arxiv 2601.15778](https://arxiv.org/abs/2601.15778) |
| Dunning-Kruger in LLMs (March 2026) | Worst-performing models express highest confidence | [arxiv 2603.09985](https://arxiv.org/html/2603.09985v1) |
| Reflexion (Shinn et al., NeurIPS 2023) | Verbal self-reflection in episodic memory improves performance significantly | [arxiv 2303.11366](https://arxiv.org/abs/2303.11366) |
| Collaborative Calibration (2024) | Multi-agent deliberation achieves calibration comparable to supervised methods, training-free | [arxiv 2404.09127](https://arxiv.org/abs/2404.09127) |

### Confidence Estimation

| Paper | Link |
|-------|------|
| Can LLMs Express Their Uncertainty? (ICLR 2024) — verbalized confidence clusters 80-100 | [arxiv 2306.13063](https://arxiv.org/abs/2306.13063) |
| Survey of Confidence Estimation and Calibration (NAACL 2024) — consistency beats verbalized | [aclanthology](https://aclanthology.org/2024.naacl-long.366/) |
| Confidence-Aware Self-Consistency (March 2026) — saves 80% tokens when confidence high | [arxiv 2603.08999](https://arxiv.org/abs/2603.08999) |
| On Verbalized Confidence Scores (Yang et al., 2024) | [arxiv 2412.14737](https://arxiv.org/pdf/2412.14737) |
| Confidence Improves Self-Consistency (ACL 2025) | [arxiv 2502.06233](https://arxiv.org/pdf/2502.06233) |
| Know When You're Wrong (March 2026) — aligning confidence with correctness | [arxiv 2603.06604](https://arxiv.org/html/2603.06604) |
| Dynamic Confidence in Evidence Accumulation (Cognition 2020) — cognitive science foundation | [sciencedirect](https://www.sciencedirect.com/science/article/abs/pii/S0010027720303413) |

### Agent Memory & Learning

| Paper | Link |
|-------|------|
| Voyager: skill library indexed by embeddings, compositional (Wang et al., 2023) | [arxiv 2305.16291](https://arxiv.org/abs/2305.16291) |
| Memory in the Age of AI Agents — survey (Dec 2025) | [arxiv 2512.13564](https://arxiv.org/abs/2512.13564) |
| Letta/MemGPT — tiered memory, skill learning, persistence | [docs.letta.com](https://docs.letta.com/concepts/memgpt/) |
| Rearchitecting Letta's Agent Loop — lessons from ReAct, MemGPT, Claude Code | [letta blog](https://www.letta.com/blog/letta-v1-agent) |

### Stopping Criteria & Budget

| Paper | Link |
|-------|------|
| SelfBudgeter — 63% token savings via self-predicted budgets (2025) | [arxiv 2505.11274](https://arxiv.org/abs/2505.11274) |
| BATS — budget-aware tool-use scaling (2025) | [arxiv 2511.17006](https://arxiv.org/html/2511.17006v1) |
| BudgetThinker — control tokens for budget-aware reasoning (2025) | [arxiv 2508.17196](https://arxiv.org/html/2508.17196v2) |
| Deep Think with Confidence — verification questions at intermediate steps | [jiaweizzhao.github.io](https://jiaweizzhao.github.io/deepconf/) |

### Agent Failure Modes

| Paper | Link |
|-------|------|
| 7 AI Agent Failure Modes (Galileo) — includes false blocker escalation | [galileo.ai](https://galileo.ai/blog/agent-failure-modes-guide) |
| Why Multi-Agent Systems Fail (March 2025) | [arxiv 2503.13657](https://arxiv.org/html/2503.13657v1) |
| Measuring Agent Autonomy (Anthropic) | [anthropic.com](https://www.anthropic.com/research/measuring-agent-autonomy) |

### Frameworks

| Framework | Link |
|-----------|------|
| DeepEval (Confident AI) — 30+ evaluation metrics, threshold-based | [github](https://github.com/confident-ai/deepeval) |
| Letta — stateful agents with persistent memory | [github](https://github.com/letta-ai/letta) |
| Langfuse — agent observability and tracing | [langfuse.com](https://langfuse.com) |

## Changelog

| Date | Change | Why |
|------|--------|-----|
| 2026-03-29 | Initial version | Research + design discussion with Dima |
| 2026-03-29 | Gotcha: CLAUDE.md changes don't reach running sessions | Session "2903" didn't update confidence or record gotcha after failed delivery — it was started before the framework was added to conductor/CLAUDE.md. Running sessions load CLAUDE.md at start, not live. New rules only apply to new sessions. |
| 2026-03-29 | Case study: 80/100 confidence, dashboard broken | Agent claimed 80/100 with 8/8 Playwright tests passing. User couldn't load dashboard — agent's own curl bombardment killed nginx. Three gaps: (1) tested feature not system — narrow test scope missed basic prerequisite, (2) agent's testing broke the environment it was testing in — side effects invisible to confidence, (3) no adversarial self-assessment at 80, (4) no gotcha recorded after failure, just patched and moved on. **Lesson: verification must include "can the user reach the thing at all" before any feature-level confidence.** |
| 2026-03-29 | Case study: flailing without root cause analysis | After dashboard failed to load, agent tried: adding allowedDevOrigins, restarting dashboard, checking cookies, killing processes — all without identifying the actual root cause. Made code changes speculatively. No confidence reported during debugging. No gotcha recorded. Pattern: agent acts like "try things until it works" instead of "diagnose → understand → fix." **Lesson: when delivery fails, stop. Diagnose root cause before touching anything. Report confidence at each step. If confidence isn't rising, escalate — don't keep patching.** |
| 2026-03-29 | Gotcha: CLAUDE.md instructions alone don't change behavior | After restart with confidence protocol in .claude/CLAUDE.md, agent received "fail" from human. Did not: report confidence, reference gotchas, stop to diagnose, or follow the protocol. Went straight to curling things. Matches LEARNINGS.md: "prompt instructions are suggestions that will be ignored when inconvenient." **The confidence protocol needs mechanical enforcement (like the stop hook), not just prompt instructions.** |
| 2026-03-30 | Gotcha G4: cleanup missions need functional DoD | Agent wrote bot-manager→meeting-api finalization mission. DoD was "grep returns clean + compose config validates." Reported 90/100. Human caught: the rename touches `BOT_MANAGER_URL` which 20 gateway proxy routes use — grep-clean would pass even if every route 502'd. **Root assumption that failed: "naming cleanup is low-risk, so text-level verification is sufficient."** Any mission that touches live wiring (env vars, URLs, service names) needs curl-level route verification in the DoD, not just grep. |
| 2026-03-30 | Protocol violation: patched before diagnosing | Same session — after human said "that was a failed delivery at high confidence," agent jumped straight to rewriting the DoD instead of following the "After human reveals you were wrong" protocol (stop → extract root gap → discuss → store gotcha). Had to be prompted "are you following the protocol?" to course-correct. Pattern matches G2 (flailing) but in a planning context rather than debugging. |
| 2026-03-30 | Gotcha G5: don't default to fallbacks | Agent proposed backward-compat fallback (`MEETING_API_URL or BOT_MANAGER_URL`) in mission plan and flagged its absence as a "CRITICAL gap." User corrected: fallbacks are never the default — clean-cut renames only. **Root assumption that failed: "renaming a live env var needs a transition period."** In this project, if something is dead it's dead. Fallbacks add complexity, mask incomplete migrations, and keep dead names alive. Only frozen external contracts (API paths, JWT issuers, wire protocols) survive. This applies generally to all renames, not just bot-manager. |
| 2026-03-30 | Gotcha G6: search ALL case variants when renaming | Team grepped `bot-manager`, `bot_manager`, `BOT_MANAGER` across 107 files. Reported 90/100. Committed and pushed. Human then found 14 `botManagerCallbackUrl` references in live wire protocol code (meetings.py, types.ts, docker.ts, index.ts, unified-callback.ts) plus `VEXA_BOT_MANAGER` env var in vexa-agent — all missed because **camelCase was never searched**. **Root assumption that failed: "three grep patterns cover all variants."** Must search kebab-case, snake_case, SCREAMING_SNAKE, camelCase, and PascalCase. Every naming convention used in the codebase's languages (Python snake_case, TypeScript camelCase, env SCREAMING_SNAKE) must be checked independently. |

---

*This is a living document. Update it when we learn something new about confidence calibration in practice.*
