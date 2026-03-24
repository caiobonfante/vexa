---
title: 'Your AI Agent Joins Your Standup Every Morning (And You Never Asked It To)'
date: '2026-03-24'
author: 'Dmitry Grankin'
authorImage: '/dmitry-grankin.jpg'
authorLinkedIn: 'https://www.linkedin.com/in/dmitry-grankin/'
heroImage: '/assets/proactive-meeting-agent.png'
slug: 'proactive-meeting-agents-scheduled-standup-automation'
summary: "First-generation AI agents wait for you to ask. Vexa agents join your meetings on schedule, transcribe, summarize, create tickets, and post to Slack — all while you sleep."
---

First-generation agents are reactive. You type a prompt, they respond. Close the session, they're gone.

Andrej Karpathy's advice: **"Remove yourself as the bottleneck. Arrange things so they're completely autonomous. The name of the game is how can you get more agents running for longer without your involvement."**

Vexa agents are proactive. They act on a schedule, chain work after events, and orchestrate multi-step pipelines without human intervention.

---

## The full pipeline

```
Schedule: "0 9 * * 1-5" (weekdays 9am)

  [T-5min]  Browser container spawns
            Restores authenticated session from MinIO
            Warms up — ready to join instantly

  [T+0]    Bot joins standup meeting
            Transcribes in real-time (sub-second WebSocket delivery)
            Dashboard shows live segments

  [During]  Participants discuss blockers, updates, action items
            Per-speaker attribution — no diarization needed

  [T+end]  Meeting ends
            meeting.completed webhook fires
            on_success callback triggers agent container

  [+10s]   Agent wakes up
            Reads transcript: vexa meeting transcript {id}
            Extracts action items, blockers, decisions
            Creates Linear tickets for anything tagged "TODO"
            Posts summary to #engineering Slack channel
            Updates knowledge/meetings/ with wiki-linked minutes
            vexa workspace save

  [+30s]   Worker container spawns
            Sends webhook to CRM with meeting metadata
            Worker exits

  [+35s]   All containers dead. Zero cost until tomorrow 9am.
```

No human triggered anything. The agent saw the schedule, joined the meeting, processed the transcript, and delivered results.

## How this compares to other approaches

| Platform | Scheduling | Spawns containers? | Meeting awareness | Self-hosted |
|----------|-----------|-------------------|-------------------|-------------|
| **OpenClaw** | "Heartbeats" (agent polls itself) | No — single process | No | Yes |
| **MindStudio** | Cron-like triggers | No — serverless functions | No | No |
| **Lindy** | Event + time triggers | No — workflow steps | No | No |
| **Trigger.dev** | Cron + queues + webhooks | Yes — but generic | No | Partial |
| **Zapier + Otter** | Zap triggers | No | Otter SaaS only | No |
| **Vexa** | Cron + relative + event callbacks | **Yes — browser/agent/worker** | **Native** | **Yes** |

The key difference: Vexa's scheduler doesn't just fire HTTP requests. It **spawns specialist containers, chains them via callbacks, and reclaims them on completion** — with native understanding of meeting lifecycle events.

## The scheduler

Built on Redis sorted sets with crash recovery, idempotency, and `on_success`/`on_failure` callbacks:

```bash
# Join standup every weekday at 9am
vexa schedule --cron "0 9 * * 1-5" meeting join --platform teams --url "..."

# Follow up 3 hours after a meeting
vexa schedule --in 3h chat "Check if Brian sent the proposal"

# Run a script daily
vexa schedule --cron "0 8 * * *" run-script daily-summary

# Periodic workspace audit
vexa schedule --every 3d chat "Run workspace audit"
```

When a scheduled `chat` job fires, the agent wakes up proactively — reads its workspace context, decides what to do, and messages the user. No human prompt needed.

---

**Current status:** Scheduler is at [confidence 90 (unit tests)](../features/scheduler/) — 16/16 tests pass, crash recovery verified. Executor needs wiring into running services. Calendar integration at [confidence 0](../features/calendar-integration/) — research complete, Google Calendar auto-join not yet built. Both are contribution-ready.
