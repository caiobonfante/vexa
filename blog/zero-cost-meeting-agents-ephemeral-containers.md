---
title: 'Zero-Cost Meeting Agents: Ephemeral Containers That Scale to Zero'
date: '2026-03-24'
author: 'Dmitry Grankin'
authorImage: '/dmitry-grankin.jpg'
authorLinkedIn: 'https://www.linkedin.com/in/dmitry-grankin/'
heroImage: '/assets/zero-cost-meeting-agents.png'
slug: 'zero-cost-meeting-agents-ephemeral-containers'
summary: "Why gluing E2B sandboxes to Recall.ai webhooks is the wrong approach. Vexa gives AI agents a runtime where meetings are a built-in primitive — with specialist containers that cost nothing when idle."
---

You're building an AI agent that processes meetings. The obvious approach: use [E2B](https://e2b.dev/) ($0.10/hr) for sandboxed compute and [Recall.ai](https://recall.ai/) for meeting bots. Wire them together with webhooks.

It works. It's also wrong.

You'll spend weeks building glue: webhook receivers, state management between two services, error handling when one fails and the other doesn't know, and a deployment that keeps both in sync. Your agent calls an external API to join meetings. It wakes up in a blank sandbox with no context. You teach it everything via prompts.

**What if meetings were a built-in primitive instead of an external API?**

---

## The problem with generic sandboxes

E2B, Modal, and AWS Bedrock AgentCore are excellent at what they do — secure, ephemeral compute for AI agents. But they're generic. Your agent wakes up in a blank Linux VM. It doesn't know what Vexa is, what meetings are, or what tools are available.

Vexa agents wake up with:

- `/system/CLAUDE.md` — instructions that teach the agent about Vexa, meetings, and available tools
- `/system/bin/vexa` — a CLI for joining meetings, reading transcripts, speaking, scheduling
- `/workspace/` — persistent files from previous sessions (knowledge, scripts, timeline)

No prompt engineering to explain your infrastructure. No tool definitions to maintain. The agent is fluent from birth.

## Specialist containers, not fat stacks

Most platforms give you one container profile. Vexa gives you three — each sized for exactly the job:

| Profile | RAM | What it does | When it dies |
|---------|-----|-------------|-------------|
| **browser** | ~1.5GB | Joins meetings, captures audio, VNC + CDP | Meeting ends + idle timeout |
| **agent** | ~200MB | Processes transcripts, runs Claude CLI, automates | Task completes |
| **worker** | ~50MB | Sends webhooks, processes files, delivers notifications | Job finishes |

The browser doesn't carry an agent (1.5GB wasted). The agent doesn't carry Chromium (1.5GB wasted). They connect via CDP over the network when needed, then die independently.

**Zero cost when idle.** No container running = no cost. The scheduler spawns containers on demand and reclaims them on completion.

## The pipeline that replaces glue code

Instead of wiring two services together, you define a pipeline:

```
Schedule: weekdays at 9am
  → Spawn browser container → join standup → transcribe
  → Meeting ends → on_success: spawn agent container
  → Agent reads transcript → summarizes → posts to Slack → creates tickets
  → on_success: spawn worker container
  → Worker sends webhook to CRM
  → All containers die. Zero cost until tomorrow.
```

This is one scheduler configuration with `on_success`/`on_failure` callbacks. No webhook plumbing between separate services. No state management. No error handling for partial failures across two providers.

## How it compares

| | E2B + Recall.ai | Modal + custom bot | **Vexa** |
|---|---|---|---|
| Meeting awareness | External API | Build it yourself | **Native primitive** |
| Agent knows tools | Prompt engineering | Prompt engineering | **System layer baked in** |
| Container profiles | One size | One size | **3 specialist profiles** |
| Pipeline orchestration | Build it yourself | Build it yourself | **Scheduler + callbacks** |
| Persistent workspace | No | No | **MinIO/Git backed** |
| Self-hosted | E2B partial | Modal no | **Fully self-hosted** |
| Cost when idle | E2B $0.05-0.10/hr | Modal per-second | **Zero** |

## Getting started

```bash
# Full stack with agent runtime
git clone https://github.com/Vexa-ai/vexa.git
cd vexa/features/agentic-runtime/deploy
docker compose up -d
```

See the [agentic-runtime feature](../features/agentic-runtime/) for architecture details and the full capability list.

---

**Current status:** Agent runtime is at [confidence 85](../features/agentic-runtime/) — MVP0-3 validated with 32 gate checks. Container profiles, scheduling, and workspace persistence all working. Post-meeting auto-trigger pipeline being wired.
