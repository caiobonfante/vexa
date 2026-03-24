---
title: "Karpathy's Agent Psychosis — And the Infrastructure It Demands"
date: '2026-03-24'
author: 'Dmitry Grankin'
authorImage: '/dmitry-grankin.jpg'
authorLinkedIn: 'https://www.linkedin.com/in/dmitry-grankin/'
heroImage: '/assets/karpathy-agent-psychosis.png'
slug: 'karpathy-agent-psychosis-what-vexa-builds'
summary: "Andrej Karpathy describes being in 'a state of AI psychosis' — delegating to agents 16 hours a day, parallelizing across repositories, demanding persistence and memory. Here's what that psychosis demands from infrastructure, and what we're building at Vexa."
---

In a [recent conversation on No Priors](https://www.youtube.com/watch?v=kwSVtQ7dziU), Andrej Karpathy described being in what he calls "a state of AI psychosis":

> "I kind of feel like I was just in this perpetual state of AI psychosis. There was a huge unlock in what you can achieve as a person. I went from 80/20 to 20/80 of writing code by myself versus delegating to agents. I don't think I've typed a line of code probably since December."

He's not alone. But the infrastructure hasn't caught up with the workflow. Here are the key themes from his conversation — and what they demand from the tools we build.

---

## "How can I have not just a single session but more of them?"

Karpathy describes wanting to parallelize:

> "You want to be Peter Steinberg basically. He has multiple, 10 repos checked out and he's just going between them and giving them work. It's not 'here's a line of code.' It's 'here's a new functionality — delegate it to agent one.' Here's a new functionality that's not going to interfere with the other one — give it to agent two."

**What this demands:** Multiple isolated agents running simultaneously. Not threads in one process — actual isolated containers with their own state, own workspace, own context.

**What Vexa builds:** [Ephemeral containers](../features/agentic-runtime/) — browser (~1.5GB), agent (~200MB), worker (~50MB) — each in its own Docker container. Spin up 10, give each a task, review their work. Zero cost when idle. Multi-tenant by design — not "one VPS per user" but a shared platform with container isolation.

---

## "It all kind of feels like skill issue"

> "It's not that the capability is not there. It's that you just haven't found a way to string it together. I didn't give good enough instructions in the agents.md file. I don't have a nice enough memory tool."

**What this demands:** Agents that come pre-configured with the right instructions and tools. The system should reduce "skill issue" — not by dumbing things down, but by giving agents context from birth.

**What Vexa builds:** A two-layer system. The [system layer](../features/agentic-runtime/) (`/system/CLAUDE.md` + `/system/bin/vexa`) is baked into every agent container — it teaches the agent what Vexa is, what tools exist, how to join meetings, read transcripts, schedule work. The [workspace layer](../features/knowledge-workspace/) (`/workspace/.claude/CLAUDE.md`) adds project-specific context. Agent wakes up fluent, not blank.

---

## "Claw-like entities with persistence and sophisticated memory"

Karpathy on what makes OpenClaw different:

> "When I say a claw I mean this layer that takes persistence to a whole new level. It's something that keeps looping, has its own little sandbox, does stuff on your behalf even if you're not looking. And then also has maybe more sophisticated memory systems that are not yet implemented in agents."

And on Peter Steinberg specifically:

> "Peter has done a really amazing job. He innovated simultaneously in like five different ways. The soul.md document — he actually crafted a personality that is compelling. A lot of the current agents don't get this correctly. The memory system. And the single WhatsApp portal to all of the automation."

**What this demands:** Persistent workspace that survives restarts. Structured memory beyond "memory compaction when context runs out." A personality that evolves with the relationship.

**What Vexa builds:** The [knowledge workspace](../features/knowledge-workspace/) — `timeline.md` (logarithmic journal), `soul.md` (agent's understanding of you), `streams/` (active topics), `knowledge/entities/` (contacts, companies, products), all connected with `[[wiki-links]]`. Inspired directly by OpenClaw's innovations — then connected to meetings, the richest source of unstructured business knowledge.

---

## "Remove yourself as the bottleneck"

> "To get the most out of the tools, you have to remove yourself as the bottleneck. You can't be there to prompt the next thing. You have to arrange things such that they're completely autonomous. The name of the game now is to increase your leverage — I put in very few tokens just once in a while and a huge amount of stuff happens on my behalf."

And on the auto-research loop:

> "Here's an objective, here's a metric, here's your boundaries of what you can and cannot do — and go."

**What this demands:** Agents that act on schedule, not on prompt. Pipeline orchestration where meeting → transcription → processing → delivery happens without human in the loop.

**What Vexa builds:** The [scheduler](../features/scheduler/) — Redis-backed, crash-safe, with `on_success`/`on_failure` callbacks that chain containers. Combined with [calendar integration](../features/calendar-integration/), the agent joins your standup every morning, processes the transcript, posts to Slack, creates tickets, and dies. You wake up to results, not tasks.

---

## "Everything should be APIs. Agents are the glue."

Karpathy on his home automation:

> "I used to use six apps, completely different apps, and I don't have to use these apps anymore. Dobby controls everything in natural language."

And the broader insight:

> "These apps shouldn't even exist. Everything should be exposed API endpoints and agents are the glue of the intelligence that tool-calls all the parts. The customer is not the human anymore — it's agents who are acting on behalf of humans."

**What this demands:** API-first tools designed for agents, not humans. MCP servers that expose capabilities as tool calls. Modular architecture where each capability is independently callable.

**What Vexa builds:** [17 MCP tools](../features/mcp-integration/) — join meetings, read transcripts, speak, chat, share screen, record, schedule. Modular services — each feature is a separate container with a REST API. [Twelve independent features](../README.md#modular--pick-what-you-need) you can use individually or compose. Designed for agents first, humans second.

---

## "A research organization is a set of markdown files"

Karpathy describes his auto-research setup:

> "program.md is my crappy attempt at describing how the auto-researcher should work. Every research organization is described by program.md — a set of markdown files that describe all the roles and how the whole thing connects."

And the meta-layer:

> "You can imagine having a better research organization. One organization can have fewer stand-ups, one can be more risk-taking. They all have code and once you have code, you can imagine tuning the code."

**What this demands:** Systems where the operating instructions are themselves code — reviewable, versionable, improvable. Not hidden in prompts or databases, but in plain markdown that agents and humans can both read and modify.

**What Vexa builds:** Every [feature](../features/) is a set of markdown files: `README.md` (what it does, why, competitive context), `.claude/CLAUDE.md` (agent instructions, gate, scope, edges), `tests/findings.md` (certainty scores with evidence). Point an AI agent at any feature directory — it reads the manifests, knows the mission, knows what's tested, knows what's broken, and starts contributing. The instructions **are** the code.

---

## "An untrusted pool of workers on the internet"

> "What I was more interested in is how you can have an untrusted pool of workers out there on the internet. If anyone gives you a candidate commit, it's very easy to verify that that commit is correct, is good."

**What this demands:** Verifiable contribution. Not "trust me, I fixed it" but "here's the evidence, the gate passed, the confidence score went from 0 to 80."

**What Vexa builds:** Every feature has a [gate](../features/README.md) — binary pass/fail with evidence-based certainty scores. Speaking bot at confidence 0? Submit a PR that runs the E2E test. If participants hear the bot speak, confidence jumps to 80+. The metric is objective, the verification is automated. Anyone — human or agent — can submit improvements that are verifiable against the gate.

---

## The psychosis is real. The infrastructure is what's missing.

Karpathy's experience maps to a clear set of infrastructure requirements:

| His experience | What's missing | What Vexa builds |
|---------------|---------------|-----------------|
| "How can I have more agents?" | Multi-tenant container orchestration | Isolated ephemeral containers, zero idle cost |
| "Skill issue — bad instructions" | Pre-configured agent fluency | System layer + workspace CLAUDE.md |
| "Persistence and memory" | File-based knowledge that survives restarts | Knowledge workspace with entities, timeline, soul |
| "Remove yourself as bottleneck" | Scheduled autonomous pipelines | Scheduler + calendar + container chaining |
| "Everything should be APIs" | Agent-first modular architecture | 17 MCP tools, 12 independent features |
| "Markdown files describe the org" | Self-describing contribution manifests | Feature READMEs + CLAUDE.md + certainty gates |
| "Untrusted pool of workers" | Verifiable improvement gates | Evidence-based confidence scores |

The psychosis is the feeling of infinite possibility constrained by inadequate infrastructure. We're building the infrastructure.

---

**Vexa is open-source.** [See the repo](https://github.com/Vexa-ai/vexa), [read the features](../features/), [join Discord](https://discord.gg/Ga9duGkVz9). Every feature has transparent confidence scores and specific "contributions welcome" items. Point your agent at a feature — it knows what to do.
