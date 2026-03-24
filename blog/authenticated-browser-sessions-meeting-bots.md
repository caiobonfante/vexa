---
title: 'Authenticated Meeting Bots: How to Join Org-Restricted Meetings with Persistent Browser Sessions'
date: '2026-03-24'
author: 'Dmitry Grankin'
authorImage: '/dmitry-grankin.jpg'
authorLinkedIn: 'https://www.linkedin.com/in/dmitry-grankin/'
heroImage: '/assets/authenticated-browser-sessions.png'
slug: 'authenticated-browser-sessions-meeting-bots'
summary: "Meeting bots get rejected from org-restricted meetings because they join as anonymous guests. Vexa's remote browser lets a human authenticate once via VNC, then the agent takes over for all future meetings — with persistent cookies and session state."
---

Every meeting bot has the same problem: it joins as an anonymous guest. Org-restricted meetings reject it. Lobby approval is required. Some organizations block external participants entirely.

Browserbase raised $40M at a $300M valuation selling headless browsers for AI agents. Their use case: web scraping, form filling, testing. They can't help you join a meeting.

**Vexa's remote browser does something different: a human authenticates once, then the agent handles all future meetings as an authenticated user.**

---

## The problem

Meeting bots launch fresh Chromium in incognito mode. No cookies, no sessions, no identity. When they try to join an org-restricted Teams or Google Meet call:

- Microsoft Teams: "You need to be signed in with an organizational account"
- Google Meet: "This meeting is restricted to people in your organization"
- Both: sitting in the lobby, waiting for someone to admit an unknown guest

There's no fix for this with incognito browsers. You need persistent authentication.

## The solution: human authenticates, agent automates

Vexa's remote browser container runs Chromium with three access methods simultaneously:

| Access | Who uses it | What for |
|--------|------------|---------|
| **VNC** | Human | See the browser, click through OAuth flows, solve CAPTCHAs, complete MFA |
| **CDP** | Agent (Playwright) | Automate navigation, join meetings, interact with pages programmatically |
| **SSH** | Developer | Shell access for debugging |

**The workflow:**

1. Human opens VNC in the dashboard → sees live Chromium desktop
2. Human logs into Teams/Google (handles OAuth, MFA, CAPTCHAs)
3. Human clicks "Save" → browser state (cookies, localStorage, IndexedDB) syncs to MinIO
4. Container can die — state is saved
5. Next meeting: container spawns, restores state from MinIO, agent joins as the authenticated user
6. No re-authentication needed until cookies expire

## How this compares to Browserbase

| Capability | Browserbase ($300M) | Browserless | Vexa Remote Browser |
|-----------|-------------|-------------|---------------------|
| Headless browser | Yes | Yes | Yes |
| CDP/Playwright | Yes | Yes | Yes |
| VNC (human sees what agent sees) | No | No | **Yes** |
| Human + agent simultaneously | No | No | **Yes** |
| Persistent auth across sessions | No (ephemeral) | No | **Yes** (MinIO sync) |
| Meeting attendance | No | No | **Yes** |
| Audio capture + transcription | No | No | **Yes** |
| Self-hosted | No | Partial | **Yes** |
| Cost | $0.10-0.12/hr | $0.05-0.10/hr | Your infrastructure |

The unique capability is **dual control** — human and agent on the same browser at the same time. Human handles judgment calls (OAuth, CAPTCHAs). Agent handles automation (join meeting, navigate, transcribe).

## Persistent state

Two layers, both persisted to MinIO:

```
/workspace/              ← user files (scripts, data) — synced to MinIO or Git
/tmp/browser-data/       ← Chromium profile (cookies, localStorage, IndexedDB) — synced to MinIO
```

On container start: download both from MinIO. On save: upload both. On next start: everything restored — logged-in sessions, saved passwords, localStorage state.

## Use cases beyond authenticated meetings

- **Pre-authenticated dashboards** — agent opens internal Grafana, takes screenshots, posts to Slack
- **Web automation with persistent state** — agent logs into SaaS tools, runs workflows, maintains sessions
- **Testing** — human sets up state via VNC, agent validates via CDP
- **Demo environments** — persistent browser state for repeatable demos

---

**Current status:** Remote browser is at [confidence 30](../features/remote-browser/) — container builds, VNC accessible, CDP works. MinIO persistence for browser profiles and authenticated meeting join flow are the main gaps. See the [feature README](../features/remote-browser/) for what's needed.
