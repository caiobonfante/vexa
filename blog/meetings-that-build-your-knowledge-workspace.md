---
title: 'Meetings That Build Your Knowledge: How Vexa Agents Maintain a Knowledge Graph From Your Calls'
date: '2026-03-24'
author: 'Dmitry Grankin'
authorImage: '/dmitry-grankin.jpg'
authorLinkedIn: 'https://www.linkedin.com/in/dmitry-grankin/'
heroImage: '/assets/knowledge-workspace.png'
slug: 'meetings-that-build-your-knowledge-workspace'
summary: "Your meetings contain contacts, decisions, and action items — but they vanish after the call. Vexa agents automatically extract entities, maintain wiki-linked knowledge, and build a personal knowledge graph that grows with every meeting."
---

You have 6 meetings today. By tomorrow, you'll remember maybe 30% of what was discussed. The contacts mentioned, the decisions made, the follow-ups promised — most of it evaporates.

Otter gives you a transcript. Fireflies gives you a summary. Neither remembers who Brian Steele is, that he's VP of Engineering at Acme Corp, that you discussed pricing last Tuesday, or that you have a follow-up scheduled for Thursday.

**What if your AI agent maintained a knowledge graph that builds itself from your meetings?**

---

## The workspace

Every Vexa agent gets a persistent workspace — a directory of markdown files that serves as its long-term memory. The [knowledge template](../features/knowledge-workspace/) gives it structure:

```
timeline.md              — where you've been, where you are, where you're going
soul.md                  — agent's understanding of you (what works, what doesn't)
streams/                 — active working topics (wiki-linked markdown files)
knowledge/
  entities/
    contacts/            — people profiles, auto-extracted from meetings
    companies/           — organization profiles
    products/            — product/project profiles
  meetings/              — meeting minutes with [[wiki-links]]
  action-items/          — tracked per meeting
scripts/                 — automation, scheduled via vexa schedule
```

Files are the source of truth — not conversation history. Sessions may reset, but the workspace persists across container restarts via MinIO or Git.

## How meetings feed the knowledge graph

After every meeting, this happens automatically:

1. **Meeting ends** → `transcript.ready` webhook fires
2. **Agent container wakes up** (scheduler `on_success` callback)
3. **Reads transcript** via `vexa meeting transcript {id}`
4. **Extracts entities** → creates or updates `knowledge/entities/contacts/brian-steele.md`
5. **Creates meeting minutes** → `knowledge/meetings/2026-03-24-renewal-call.md` with `[[Brian Steele]]`, `[[Acme Corp]]` wiki-links
6. **Tracks action items** → schedules follow-ups via `vexa schedule`
7. **Updates timeline** with events and deadlines mentioned
8. **Saves workspace** → `vexa workspace save` persists to storage

Nobody triggered this. The meeting produced structured knowledge automatically.

## How it compares to other memory systems

| Platform | Memory model | Meetings feed it? | Entity graph | Self-hosted |
|----------|-------------|-------------------|-------------|-------------|
| **OpenClaw** | MEMORY.md + SOUL.md + daily logs | No | No | Yes |
| **Mem0** (48K stars) | Vector + graph + KV store | No | API-based | No (SaaS) |
| **Obsidian + AI** | Markdown + wiki-links | Manual note-taking | Manual | Yes (local) |
| **Clay/Attio** | CRM with AI enrichment | Via integrations | Yes | No |
| **Vexa** | Markdown + wiki-links + entities + streams + timeline + soul | **Automatic** | **Contacts, companies, products** | **Yes** |

Every other memory system is disconnected from meetings. You manually feed information in. Vexa's workspace is populated by the meeting pipeline.

## Inspired by the best

Andrej Karpathy describes the ideal AI agent as a "claw-like entity with persistence — something that keeps looping, has its own sandbox, does stuff on your behalf even if you're not looking, with sophisticated memory systems."

Peter Steinberg's [OpenClaw](https://github.com/openclaw/openclaw) pioneered `SOUL.md` and `MEMORY.md` — giving agents personality and persistent memory. Vexa takes this further by connecting the memory to meetings, the richest source of unstructured business knowledge.

The workspace also draws from [Obsidian's](https://obsidian.md/) wiki-link knowledge graph and the Quorum project's workspace system — adapted for Vexa's container architecture and meeting pipeline.

## Who this is for

- **Founders/executives** with 5-10 meetings/day who lose 90% of the information
- **Sales teams** who need contacts, decisions, and follow-ups extracted automatically
- **Consultants** juggling multiple clients — each with their own workspace
- **Anyone** who's tried Otter + Notion + a CRM and wishes they were connected

---

**Current status:** Knowledge workspace is at [confidence 60](../features/knowledge-workspace/) — template and persistence working, entity extraction pipeline not yet built. This is a high-impact contribution area — see the feature README for what's needed.
