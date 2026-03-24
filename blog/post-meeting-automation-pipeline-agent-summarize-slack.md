---
title: 'Post-Meeting Automation: Meeting Ends → Agent Summarizes → Slack Gets the Notes'
date: '2026-03-24'
author: 'Dmitry Grankin'
authorImage: '/dmitry-grankin.jpg'
authorLinkedIn: 'https://www.linkedin.com/in/dmitry-grankin/'
heroImage: '/assets/post-meeting-pipeline.png'
slug: 'post-meeting-automation-pipeline-agent-summarize-slack'
summary: "Meetings end and nothing happens. Someone was supposed to write the summary. Nobody did. Vexa's post-meeting pipeline turns every meeting into action — automatically, with zero human intervention."
---

Here's what happens after most meetings: nothing. Someone was supposed to write the summary. Someone was supposed to update the CRM. Someone was supposed to file the ticket. Nobody did.

Otter sends you a summary email. Fireflies pushes to CRM via Zapier. These are one-step automations. They can't chain: summarize → extract action items → create tickets → notify the team → update the knowledge base.

**Vexa's post-meeting pipeline does the full chain — in ephemeral containers that cost nothing when idle.**

---

## The pipeline

```
Meeting ends
  │
  ▼
  transcript.ready webhook fires
  │
  ▼
  Scheduler on_success callback triggers agent container (~200MB)
  │
  ▼
  Agent wakes up, reads transcript:
    vexa meeting transcript {meeting_id}
  │
  ▼
  Agent processes:
    → Summarizes discussion (3-5 bullet points)
    → Extracts action items with owners
    → Identifies decisions made
    → Updates knowledge/entities/ with new contacts
    → Updates timeline.md with deadlines mentioned
  │
  ▼
  Agent delivers:
    → Posts summary to #engineering Slack channel
    → Creates Linear tickets for each action item
    → Sends follow-up email draft to attendees
    → vexa workspace save (persist knowledge)
  │
  ▼
  on_success: spawn worker container (~50MB)
    → Sends webhook to CRM with structured meeting data
    → Worker exits
  │
  ▼
  All containers dead. Zero cost.
```

No Zapier. No n8n (though Vexa [works with n8n](n8n.md) too). No glue code. One pipeline, defined by scheduler callbacks.

## What makes this different from Otter + Zapier

| | Otter + Zapier | Fireflies + CRM | **Vexa pipeline** |
|---|---|---|---|
| **Summarize** | Otter summary email | Fireflies summary | Agent processes full transcript |
| **Action items** | Manual extraction | Template-based | Agent extracts with context |
| **Create tickets** | Zapier step | Not available | Agent creates directly (Linear API, Jira API, etc.) |
| **Update knowledge** | Not available | Not available | **Agent updates wiki-linked entity files** |
| **Custom logic** | Zapier steps (limited) | Zapier steps (limited) | **Arbitrary code in agent container** |
| **Self-hosted** | No (Otter SaaS + Zapier SaaS) | No | **Yes — everything on your infra** |
| **Cost** | Otter $17/seat + Zapier $20+/mo | Fireflies $19/seat + Zapier | **Infrastructure cost only** |

The key difference: Vexa agents run arbitrary code in isolated containers. They're not limited to "pick a Zapier action." They can call any API, run any script, process any data — then die.

## Setting it up

**Step 1:** Configure post-meeting webhook in docker-compose:

```yaml
bot-manager:
  environment:
    - POST_MEETING_HOOKS=http://agent-api:8100/api/webhooks/meeting-completed
```

**Step 2:** The agent's workspace CLAUDE.md tells it what to do when a meeting ends. The default knowledge template already includes instructions for entity extraction, timeline updates, and action item tracking.

**Step 3:** For Slack/Linear/CRM delivery, add API keys to the agent's workspace or environment. The agent uses them via scripts in `scripts/`.

## Two transcription modes

| Mode | When | How |
|------|------|-----|
| **Real-time** | During the meeting | Sub-second WebSocket delivery, live dashboard |
| **Post-meeting** | After the meeting ends | One Whisper pass over full recording — cheaper, more accurate |

Choose based on your needs. Real-time for live dashboards and in-meeting interaction. Post-meeting for best accuracy and lowest cost.

---

**Current status:** Post-meeting transcription at [confidence 85](../features/post-meeting-transcription/) — pipeline works with 100% speaker accuracy (2 speakers). Webhooks at [confidence 85](../features/webhooks/) — envelope standardized. The end-to-end pipeline (webhook → agent → delivery) needs the agent-api webhook receiver endpoint (~20 lines of code). See the [agentic-runtime feature](../features/agentic-runtime/) for contribution details.
