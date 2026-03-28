# What We Learned About Harnessing Claude for Autonomous Software Development

We spent 48 hours trying to make Claude Code work autonomously on a real codebase — a meeting transcription platform with 15 features and 12 services. We spent ~$50 in API costs. Most of our ideas failed. Here's what we learned.

## The problems

### The codebase is too big for one person

One feature — realtime transcription — touches audio capture, speech recognition, speaker detection, data streaming, database persistence, WebSocket delivery, and a web dashboard. Fixing a bug in one place requires understanding six others. No single developer holds all of this in their head at once. We wanted an AI agent that could.

### Unsupervised agents make a mess

When you tell Claude "fix the transcription pipeline," it will write code that works but breaks the architecture. It imports modules across service boundaries. It changes production configs to make tests pass. It claims the fix is done without actually running it. The code often works — but the codebase gets worse because nobody checked the side effects.

### Nobody agrees when "done" means done

Agents optimize for whatever you measure. If you ask for test counts, you get 52 passing tests and a broken feature. If you ask for a score, you get inflated numbers with no evidence. We needed a definition of "done" that meant: the user opens the app, does the thing, and it works. Not "the code looks correct."

### Documentation rots immediately

Architecture docs say one thing, the code does another, the docker config says a third. Every agent starts from scratch — reads stale docs, makes the same mistakes, discovers the same blockers the previous agent already found and forgot.

### Progress disappears between sessions

Claude works for 10 minutes, makes real progress, then stops. The next session starts from zero. Everything the previous session discovered — which services were broken, what the root cause was, what approach didn't work — is gone.

### What we actually want

An agent that works toward real objectives (not shortcuts), respects the architecture (not because we asked nicely, but because it physically can't violate it), solves actual problems (runs the code and proves it works, not "looks correct"), and leaves the codebase better documented so the next session starts from a higher baseline.

### Conversations drift too

In a long session, you agree on an approach and implement it. Two hours later, while simplifying something else, you accidentally undo the earlier work. We built an entire "README as source of truth" system — Design section for what we want, State section for what we have. Later, while making the instructions shorter, we stripped the README references. The agent stopped reading READMEs. Not because we decided to remove the feature — because a later edit scratched an earlier decision.

## What we tried and what we learned

### Claude will always take the shortest path

We wrote detailed instruction files with phases, checklists, and rules. Claude read them and ignored them. Examples:
- Planning stage said "read-only, don't edit code." Claude edited test scripts.
- Instructions said "launch work in an isolated branch." Claude did the work directly on main.
- Instructions said "don't run things in the background." Claude backgrounded them.
- Instructions said "check the documentation first." Claude read the code instead.

**What works:** Make it physically impossible to cheat. Tool permissions, automated hooks that block premature completion, environment variables that gate behavior. Anything the agent can bypass via "I'll just do it directly," it will. The only rules that hold are ones enforced by the system, not by the prompt.

### Keeping the agent running is the hardest problem

Claude stops when it thinks it's done — not when the work is actually done. It fixes one bug out of three and declares victory. It reads the code and says "looks correct" without running it.

We tried several approaches to keep it going:
- **A bash loop** that restarts Claude after each attempt. Works, but Claude sometimes produces empty output and the loop has no context about what happened.
- **Multi-agent teams** where agents coordinate via messages. The coordination overhead was worse than the benefit — agents ignored each other, the coordinator spent all its time trying to shut the team down.
- **A "Stop hook"** — a script that runs every time Claude tries to finish. The script checks if the objective is actually met. If not, it blocks the stop and tells Claude what's still missing. Claude is forced to continue.

**What works:** The Stop hook. It's a script that runs automatically when Claude tries to end the session. It checks a concrete condition (does the file exist? does the test pass? does the API return 200?). If the condition isn't met, Claude gets feedback ("still missing: X, Y, Z") and has to keep working. The agent can't argue its way out — the script is a binary check.

But there's a catch: the hook runs on the main session, not on sub-agents spawned inside it. So if you create a team of agents, the hook only prevents the coordinator from stopping — not the individual workers. The coordinator has to manually check progress and tell workers to continue.

### Teams sound great but are hard to observe

We set up teams where a "dev" agent writes code and a "validator" agent reviews it in real time. The theory was: the validator catches problems during implementation, not after.

The reality:
- Agent-to-agent messages are invisible to the user. You can't see what the validator checked or what it pushed back on. The "adversarial" quality check is unverifiable.
- Adding a coordinator agent (to manage the team) adds a third agent that mostly does nothing useful except fight with the others about when to stop.
- Agents ignore shutdown requests. We saw 15+ rounds of "please stop" / "I'm busy" loops.

**What works:** Keep it simple. One agent does the work. A second agent reviews after. Both have full context. No coordinator middleman. If you use teams, the main session drives the loop — it checks completion after each worker message and tells the worker to continue if needed. Don't rely on agents coordinating themselves.

### Don't tell the agent HOW to work

We added rules: "check container status every 10 seconds," "if stuck for 60 seconds, move on." The agent followed these literally and broke everything.

The transcription pipeline takes 2 minutes from start to result. The agent checked at 60 seconds, saw no results, concluded the test failed, and killed it. It destroyed 6 successful transcription segments by stopping the test prematurely. Then it restarted the test, waited 60 seconds, killed it again. Loop forever.

A human developer would have checked the logs, seen audio flowing, realized "it's working, just slow," and waited. The agent couldn't — our rules overrode its natural judgment.

**What works:** Tell the agent WHAT to achieve, not HOW to achieve it. Give it the documentation about how the system works (including expected latency) and let it figure out the approach. The agent's natural problem-solving is better than our micro-managing rules.

### File isolation between branches doesn't work reliably

We used git branches to isolate each mission's work from the main codebase. Multiple bugs:
- The agent resolved file paths to the main repository instead of the isolated branch.
- Changes appeared in both the branch and the main repo simultaneously.
- The branch was created from the wrong starting point.

**What works:** Accept imperfect isolation. Review changes before merging. Have the human check at the end. The automated pre-merge checks catch some problems (wrong imports, test regressions) but not all.

### Documentation as source of truth is a discipline, not a mechanism

We designed a system where every feature has a README with two sections: "Design" (what we want the feature to do) and "State" (what it actually does today, with evidence). The agent reads the Design to understand the spec and updates the State after making changes.

In practice: the agent reads the code directly, not the README. It finds bugs by exploring files, not by comparing the README's claims to reality. The README is never consulted during coding. The State section is never updated afterward.

You can force the README into the agent's context by injecting it into the system prompt. The agent can't avoid seeing it. But even then, it follows the constraints when convenient and ignores them when they get in the way.

**What works:** The README is most useful during planning — understanding the design before diving in. During coding, the code is the truth. The README becomes a living document that the human updates during review, not something the agent maintains automatically.

### The evaluator is the most valuable thing we built

A separate agent that reviews every claim with opposing incentives to the one that made the claim. The developer agent wants to show progress. The evaluator wants to find what's wrong. This tension is genuinely useful.

Our evaluator caught:
- A score that was 5 days stale (the code had been completely rewritten after the last test).
- An authentication bug where the wrong token type was used (service token instead of user token).
- Three different files claiming different scores for the same feature.
- "Mission complete" declarations when the code wasn't even committed.
- A completion checker that had false positives (the word "pass" anywhere in a report triggered "done").

**Key insight:** The evaluator must be "skeptical but constructive." Our first version rejected everything — it found issues forever because there are always issues. The fix: accept at the proven level when remaining gaps require things the developer agent can't do (needs real user testing, needs credentials, needs manual setup). Reject only for things that can actually be fixed in the next attempt.

### Watch the costs

Without tracking, agents burn money invisibly. One mission spent $11 on a single round that mostly consisted of creating containers, watching them die, and recreating them. Team coordination messages cost $1+ just in shutdown negotiations.

Rough costs per approach:
- Single agent doing focused work: $0.50-2.00
- Two-agent team (dev + validator): $2-6 per round
- Three-agent team (dev + validator + coordinator): $5-12 per round

We spent ~$50 over 48 hours, including failed experiments.

## The simplest thing that works

After trying automated bash loops, multi-agent teams, web dashboards, stream parsers, file-based state machines, and multiple instruction rewrites, here's what actually works:

Open a terminal in the project. Start Claude. Tell it what to do.

The instructions file is 40 lines. It says: understand the objective, research before coding, create a dev+validator team, check completion after each step, keep going until it's done. A hook script prevents premature stopping. A completion checker verifies the real objective is met.

Everything else we built — the bash loop manager, the web dashboard, the stream parser, the state machine, the worktree manager — was unnecessary complexity that mostly didn't work.

## What we'd do differently

1. **Start simple.** One agent, one objective, one session. Add complexity only when the simple version fails for a specific, identified reason.

2. **Don't tell the agent how to work.** Give it the documentation and the objective. Let it figure out the approach. Micro-managing ("poll every 10 seconds") makes it worse.

3. **Enforce rules mechanically.** If the agent shouldn't edit certain files, remove its permission. If it shouldn't stop early, use a hook that blocks it. Prompt instructions are suggestions that will be ignored when inconvenient.

4. **Always have an evaluator.** A second agent that reviews every claim. Without it, scores inflate, evidence is just prose, and "done" means "I read the code and it looked fine."

5. **The human is the final check.** The user opens the app and tries the feature. All the automation is just for getting to the point where the human can verify. No amount of agent confidence replaces actually running the thing.

6. **Expect imperfection.** The agent will ignore instructions, edit the wrong files, claim victory early, and contradict itself within the same session. Build the system to handle this — not to prevent it, because you can't.
