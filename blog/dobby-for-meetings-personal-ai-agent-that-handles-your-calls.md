---
title: "Dobby for Meetings: Build a Personal AI Agent That Handles Your Calls"
date: '2026-03-24'
author: 'Dmitry Grankin'
authorImage: '/dmitry-grankin.jpg'
authorLinkedIn: 'https://www.linkedin.com/in/dmitry-grankin/'
heroImage: '/assets/dobby-for-meetings.png'
slug: 'dobby-for-meetings-personal-ai-agent-that-handles-your-calls'
summary: "Karpathy built Dobby — an AI agent that controls his home through WhatsApp. Here's how to build the same thing for your meetings: an agent that joins your calls, remembers everyone, and handles the follow-ups."
---

Andrej Karpathy built [Dobby](https://www.youtube.com/watch?v=kwSVtQ7dziU) — an AI agent that controls his entire home through WhatsApp. Lights, HVAC, shades, pool, security cameras. He used to need six different apps. Now he texts "Dobby, sleepy time" and everything turns off.

> "I used to use six apps, completely different apps, and I don't have to use these apps anymore. Dobby controls everything in natural language. It's amazing."

Meetings have the same problem. You need Otter for transcription, Notion for notes, a CRM for contacts, Linear for tickets, Slack for delivery, Google Calendar for scheduling. Six tools, none of them connected.

**What if you had a Dobby for meetings?**

---

## What a meeting Dobby looks like

You text your agent (Telegram, WhatsApp, web dashboard — wherever you are):

> **You:** "Join my 2pm standup and send me notes after"

The agent:
1. Schedules a bot to join at 1:59pm
2. Bot joins, transcribes the full meeting with per-speaker attribution
3. Meeting ends — agent wakes up automatically
4. Reads the transcript, extracts key points:
   - Sarah is blocked on the API migration
   - Mike needs the design review by Friday
   - New customer Acme Corp mentioned — pricing discussion needed
5. Creates a Linear ticket: "API migration blocker — Sarah"
6. Posts to #engineering: "Standup summary: 3 action items..."
7. Updates its knowledge base: `knowledge/entities/contacts/sarah.md`, `knowledge/meetings/2026-03-24-standup.md`
8. Texts you back: "Done. 3 action items, posted to Slack. Sarah is blocked on API migration — want me to schedule a sync with her?"

You reply: "Yes, tomorrow 10am"

Agent schedules the meeting, sends a calendar invite, and sets a bot to join that one too.

---

## How it's built (the architecture)

Karpathy's Dobby uses OpenClaw on a VPS with WhatsApp as the interface. A meeting Dobby uses Vexa with the same pattern — but with meetings as a native capability:

```
You (Telegram/Web/WhatsApp)
  │
  ▼
Agent API — receives your message, routes to agent container
  │
  ▼
Agent Container (~200MB, ephemeral)
  ├── /system/CLAUDE.md — knows Vexa tools (join meeting, read transcript, schedule)
  ├── /workspace/ — your persistent knowledge (entities, timeline, scripts)
  └── Claude CLI — processes your request
       │
       ├── vexa schedule --at "2026-03-24T13:59:00Z" meeting join --url "..."
       ├── vexa meeting transcript {id}  (after meeting)
       ├── vexa schedule --at "2026-03-25T10:00:00Z" chat "Sync with Sarah"
       └── vexa workspace save
```

The agent is ephemeral — it spawns when you message, does its work, saves state, dies. Next message: respawns with full context from workspace files.

## Dobby vs Meeting Dobby

| | Karpathy's Dobby | Meeting Dobby (Vexa) |
|---|---|---|
| **Interface** | WhatsApp | Telegram, web, meeting chat |
| **Controls** | Lights, HVAC, Sonos, cameras | Meetings, transcripts, bots, schedules |
| **Memory** | OpenClaw MEMORY.md | Workspace: timeline, entities, streams, soul |
| **Scheduling** | OpenClaw heartbeats | Redis-backed scheduler with crash recovery |
| **Proactive** | Security camera alerts | Meeting summaries, follow-up reminders, audit |
| **Multi-user** | Single user | Multi-tenant — works for your whole team |
| **Self-hosted** | VPS | Docker Compose |

## The "six apps" problem for meetings

Just like Karpathy replaced six home automation apps with one WhatsApp chat, a meeting Dobby replaces:

| App | What it does | Meeting Dobby |
|-----|-------------|---------------|
| **Otter/Fireflies** ($17-20/seat) | Transcription | `vexa meeting join` + real-time transcription |
| **Notion** | Meeting notes | `knowledge/meetings/` auto-populated |
| **CRM** (Salesforce, HubSpot) | Contact tracking | `knowledge/entities/contacts/` auto-extracted |
| **Linear/Jira** | Action items → tickets | Agent creates tickets from transcript |
| **Slack** | Delivery | Agent posts summaries to channels |
| **Google Calendar** | Scheduling | `vexa schedule` + calendar integration |

One agent, one chat interface, all your meetings. Texts you results, remembers context, acts proactively.

## Karpathy's insight

> "What people have in their mind of what an AI is — it's not actually what an LLM is. What they think of is this persona identity that they can tell stuff and it remembers it. It's just kind of an entity behind a WhatsApp."

That's exactly what a meeting Dobby is. Not a transcription API. Not a bot framework. A **persona** that handles your meetings, remembers your contacts, follows up on your action items, and texts you when something needs your attention.

---

## Get started

```bash
git clone https://github.com/Vexa-ai/vexa.git
cd vexa/features/agentic-runtime/deploy
docker compose up -d
```

Set up your Telegram bot token, send it a message: "Join my next meeting." The agent takes it from there.

See the [knowledge workspace template](../features/knowledge-workspace/) for the full workspace structure — timeline, soul, entities, streams, scripts.

---

**Current status:** Agent chat via Telegram and web dashboard is working ([confidence 85](../features/agentic-runtime/)). Knowledge workspace template is deployed ([confidence 60](../features/knowledge-workspace/)). Calendar auto-join is [not yet built](../features/calendar-integration/) — currently you tell the agent when to join. Entity extraction from transcripts is the key missing piece.
