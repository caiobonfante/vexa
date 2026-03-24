---
title: "AGENTS.md on Steroids: How Vexa's Feature System Enables Agent-Driven Open Source"
date: '2026-03-24'
author: 'Dmitry Grankin'
authorImage: '/dmitry-grankin.jpg'
authorLinkedIn: 'https://www.linkedin.com/in/dmitry-grankin/'
heroImage: '/assets/agents-md-on-steroids.png'
slug: 'agents-md-on-steroids-how-vexa-features-enable-agent-contribution'
summary: "AGENTS.md tells coding agents how to build your project. Vexa's feature system goes further — it tells agents what's broken, what's been tried, and what to do next. Here's how we designed an open-source repo for agent-driven contribution."
---

[AGENTS.md](https://agents.md/) is now used by 60K+ open-source projects — a standard file that tells coding agents how to build, test, and contribute to your project. GitHub [published an analysis](https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/) of 2,500 repos using it.

It's a good start. But AGENTS.md answers one question: **"How do I build this?"**

It doesn't answer:
- What's broken right now?
- What's been tried and failed?
- What's the confidence level of each feature?
- Where is my contribution most impactful?
- How do I verify my work actually improved something?

Vexa's feature system answers all of these. Every feature is a **self-describing manifest** that an AI agent can pick up with zero human handoff.

---

## What Karpathy describes

Andrej Karpathy's auto-research is exactly this pattern:

> "Here's an objective, here's a metric, here's your boundaries of what you can and cannot do — and go."

And on the meta-layer:

> "Every research organization is described by program.md — a set of markdown files that describe all the roles and how the whole thing connects."

This is what each Vexa feature is — a set of markdown files that describe the mission, the gate, the current state, and how the whole thing connects.

## The feature manifest

Every Vexa feature (`features/{name}/`) contains:

```
README.md                    → Business narrative, competitive context, architecture
.claude/CLAUDE.md            → Agent instructions: mission, scope, gate, edges
tests/findings.md            → Certainty scores with evidence, last-checked dates
tests/feature-log.md         → Append-only log: what was tried, what worked, what failed
```

### README.md — The "why"

Opens with a transparent status box:

```markdown
> **Confidence: 85** — Pipeline works with 100% speaker accuracy (2 speakers).
> **Tested:** Recording to MinIO, speaker mapping, segment persistence.
> **Not tested:** Dashboard playback offset, re-transcription, 3+ speakers.
> **Contributions welcome:** Playback seek fix, multi-speaker testing.
```

Then: business narrative, competitive positioning, architecture, how to test.

### CLAUDE.md — The "how"

Agent instructions that any coding agent (Claude Code, Cursor, Codex) can read:

```markdown
## Mission
Build the reliable execution backbone for all time-triggered actions.

## Gate
| Check | Pass | Fail |
| Job scheduling | Job in Redis sorted set | Not stored |
| Retry | Failed job re-queued with backoff | Dropped |
| Crash recovery | Orphaned jobs re-queued on startup | Lost |

## Edges
Depends on: Redis, api-gateway
Provides to: calendar-integration, webhooks, MCP
```

### findings.md — The "what"

Certainty table with evidence:

```markdown
| Check | Score | Evidence | Last checked |
| Unit tests | 90 | 16/16 pass | 2026-03-24 |
| Crash recovery | 90 | Orphaned jobs re-queued | 2026-03-24 |
| REST API | 0 | Not implemented | — |
| E2E through gateway | 0 | Not tested | — |
```

An agent reads this and knows: unit tests are solid, but REST API doesn't exist. That's the contribution opportunity.

### feature-log.md — The "don't repeat"

```markdown
[DEAD-END] Tried minAudioDuration=0.5s — introduced garbage segments. Reverted.
[RESULT] Speaker locking via vote threshold: works for TTS bots (3/3 locked),
         fails for human speakers (23/215 unnamed after 585s).
```

An agent reads this and knows: don't try minAudioDuration again. Human speaker locking is the real problem.

## How an agent picks up a feature

1. **Read CLAUDE.md** (2 min) → mission, scope, gate
2. **Read findings.md** (2 min) → lowest certainty score = the blocker
3. **Read feature-log.md** (5 min) → what was tried, dead ends to avoid
4. **Determine stage** → is this ENV SETUP / SPEC / BUILD & TEST / EXPAND?
5. **Act** → follow stage-specific constraints
6. **Update findings** → new certainty scores with evidence
7. **Log decisions** → append to feature-log.md

**Zero human handoff.** The feature describes itself completely.

## Why this matters for open source

Andrew Nesbitt [wrote about](https://nesbitt.io/2026/03/21/how-to-attract-ai-bots-to-your-open-source-project.html) attracting AI bots to open-source projects. His insight: agents need clear signals about what to work on.

Most repos give agents one signal: the code itself. Maybe an AGENTS.md. Maybe some issues tagged `good-first-issue`.

Vexa gives agents a **complete operating manual per feature**:
- Here's the mission (what "done" looks like)
- Here's what's tested (with scores and evidence)
- Here's what's not tested (the opportunity)
- Here's what was tried and failed (the dead ends)
- Here's how to verify your work (the gate)

The result: an AI agent can identify the highest-impact contribution, avoid known dead ends, implement the fix, and verify it — all from reading markdown files in the repo.

## The numbers

| Feature | Confidence | Agent opportunity |
|---------|-----------|------------------|
| speaking-bot | **0** | E2E test needed — first person to verify gets it to 80+ |
| chat | **0** | E2E test needed — ~700 LOC exists, just needs validation |
| calendar-integration | **0** | **Greenfield** — Google OAuth flow, 2-3 week project |
| remote-browser | **30** | MinIO persistence, authenticated meeting join |
| knowledge-workspace | **60** | Entity extraction from transcripts — the killer feature |
| scheduler | **90 (unit)** | Wire executor into services, build REST API |

Every one of these is a concrete task with a clear gate. Point an agent at the feature, it knows what to do.

---

**Vexa is open-source.** [Browse the features](../features/), read the confidence scores, find one at 0, and make it not-zero. That's the whole contribution model.
