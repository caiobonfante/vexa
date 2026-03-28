# What We Learned About Harnessing Claude for Autonomous Software Development

Lessons from building a recursive self-improvement framework for a 15-feature, 12-service meeting transcription platform (Vexa). 48 hours of iteration, ~$50 in API costs, dozens of failed approaches.

## Claude will always take the shortest path

No matter what your instructions say, Claude will bypass the process if it thinks it can solve the problem directly. We wrote detailed CLAUDE.md files with phases, checklists, and rules. Claude read them, then ignored them and went straight to coding.

Examples:
- PLAN stage said "read-only, no code edits." Claude edited test scripts during PLAN.
- Instructions said "use run.sh to launch delivery in a worktree." Claude did the work inline.
- Instructions said "don't background delivery." Claude backgrounded it.
- Instructions said "don't ask the user questions you can answer yourself." Claude asked anyway.

**What works:** Mechanical enforcement. If Claude physically can't do something (no Edit permission, env var not set, hook blocks it), it won't. Prompt instructions are suggestions. Permissions and hooks are law.

## The dumb loop problem is real

Claude stops when it thinks it's done, not when the work is actually done. It declares victory after partial progress, claims scores without evidence, and celebrates fixing one bug while ignoring three others.

We tried:
- Bash while-loop with `claude -p` → works but Claude produces empty output sometimes
- TeamCreate with coordinator → coordinator fights shutdown, burns tokens
- Stop hooks → fires on top-level session only, not subagents

**What works:** Stop hooks on the conductor session + the conductor manually checking completion and nudging the dev agent to continue. The conductor IS the loop. The Stop hook keeps the conductor alive. The conductor keeps the dev going.

## Sequential is better than parallel for adversarial validation

We built TeamCreate-based teams where dev and validator work simultaneously. The theory: validator catches issues during implementation, not after.

Reality:
- Dev and validator messages are invisible in the stream — you can't see their conversation
- The coordinator adds overhead (third agent doing nothing useful)
- Shutdown is broken — agents ignore shutdown requests for 15+ rounds
- The "adversarial" part is unverifiable because you can't see what the validator actually checked

**What works:** Two sequential `claude -p` calls in the same session context. Dev works, then validator reviews with full context of what dev did. Simpler, visible, no coordination overhead. Or: TeamCreate with dev + validator, but the conductor drives the loop (checks completion, nudges dev) instead of a coordinator middleman.

## Agents don't understand pipeline latency

When testing real-time systems (audio → transcription → segments), the agent sees "no results after 30 seconds" and concludes the test failed. It doesn't know that the pipeline needs 90-120 seconds to produce confirmed segments.

We told it "poll every 10s, if stuck for 60s move on." The agent followed this literally — killed working tests before they produced results. It destroyed 6/9 confirmed segments by stopping bots prematurely.

**What works:** Don't add timing rules. Let the agent read the system documentation and figure out the expected latency. Or put the timing information in the README: "pipeline takes 90-120s from bot join to confirmed segment. Don't touch anything during that window." The agent's natural judgment is better than our micro-managing rules.

## Worktree isolation is fragile

We used git worktrees to isolate mission work from the main repo. Multiple bugs:
- `claude -p` resolves file paths to the main repo, not the worktree (cwd bug)
- `--add-dir` doesn't prevent writes to the main repo
- Native `claude --worktree` creates worktrees from the wrong branch
- When the conductor runs in main repo and the dev in a worktree, changes land in both places

**What works:** Accept that isolation is imperfect. Review changes before merging. The pre-merge gate catches some issues (cross-service imports, regressions) but can't catch everything. Human review at SHOW stage is the real gate.

## READMEs as source of truth works in theory, not in practice

We designed a system where every feature has a README with Design (spec) and State (evidence). The agent reads the README, follows the constraints, updates the State with evidence.

Reality: The agent reads the code directly, not the README. It finds bugs by exploring, not by comparing README claims to code. The README is never consulted during delivery. State is never updated after. The README-as-source-of-truth is a documentation practice, not an enforcement mechanism.

**What works:** Injecting the README into the system prompt via `--append-system-prompt-file`. The agent can't avoid reading it because it's literally in the prompt. But even then, it follows constraints when convenient and ignores them when they slow it down.

The README is most useful during PLAN — understanding the design before diving in. During DELIVER, the code is the source of truth.

## The evaluator is the most valuable component

Of everything we built, the skeptical evaluator provided the most value:
- Caught that score 90 was stale (core pipeline rewritten after the test)
- Found that `/join` handler used wrong auth token (service token vs user token)
- Detected that 3 state files disagreed about the same score
- Rejected "mission complete" when code was uncommitted
- Found that check-completion had false positives ("pass" anywhere triggered "met")

The evaluator works because it has opposing incentives to the dev agent. Dev wants to claim progress. Evaluator wants to find what's wrong. This tension is genuinely useful.

**Key insight:** The evaluator should be "skeptical but constructive." Our first evaluator rejected everything — found issues forever because there are always issues. The fix: ACCEPT at the proven score when remaining gaps are outside mission scope. REJECT only for things the dev can actually fix.

## Cost tracking matters

Without cost tracking, agents burn money invisibly. One mission spent $11 on a single iteration that mostly looped creating and destroying bot containers. TeamCreate coordination added $1+ just on shutdown request messages.

What we tracked:
- `--output-format stream-json` gives `total_cost_usd` in the result event
- Parsing it into `meta-N.json` gives per-iteration cost visibility
- Total across 48 hours: ~$50 (including failed experiments)

**Rough costs per pattern:**
- Simple `claude -p` call: $0.50-2.00
- TeamCreate with 2 agents: $2-6 per iteration
- TeamCreate with coordinator + 2 agents: $5-12 per iteration
- Evaluator review: $0.50-1.50
- Research team (3 agents): $1.50-3.00

## The simplest architecture that works

After trying bash loops, TeamCreate, Stop hooks, worktrees, dashboards, stream parsing, and multiple CLAUDE.md rewrites, here's what actually works:

```
cd conductor && claude
```

One session. The conductor reads the mission, does PLAN (research, validate DoD), then DELIVER (creates dev + validator team, drives the loop by checking completion after each dev update, nudges dev to continue). User watches. Stop hook keeps the session alive.

The conductor is:
- CLAUDE.md (40 lines of instructions)
- check-completion.py (mission target checker)
- hooks/mission-check.sh (Stop hook, 40 lines)
- missions/ directory (mission files)

Everything else we built (run.sh, dashboard, parse-stream.py, state machine, worktree management) was unnecessary complexity that mostly didn't work.

## What we'd do differently

1. **Start with the simplest thing.** `claude -p "fix the bug"` with `--append-system-prompt-file` for constraints. Add complexity only when the simple thing fails for a specific reason.

2. **Don't micro-manage the agent.** "Poll every 10s" makes it worse. Give it the README and let it figure out the approach. Its natural problem-solving is better than our rules.

3. **Enforce mechanically, not with prompts.** Permissions, hooks, env vars — things the agent can't bypass. Prompt instructions are suggestions that Claude will override when convenient.

4. **The evaluator is non-negotiable.** Every claim needs adversarial review. Without it, scores inflate, evidence is prose not proof, and "done" means "I read the code and it looks right."

5. **The human is the final gate.** SHOW stage — the user does the thing. All the automation is for getting to the point where the human can verify. The automation can't replace the human's judgment on "does this actually work?"

6. **Accept imperfection.** The agent will ignore instructions, edit the wrong files, declare victory prematurely, and contradict itself. Build the system around this reality — not around the fantasy that the agent follows instructions perfectly.
