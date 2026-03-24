---
title: 'Open-Source Meeting Dashboard — Clone, Run, Vibe Code'
date: '2026-03-03'
author: 'Dmitry Grankin'
authorImage: '/dmitry-grankin.jpg'
authorLinkedIn: 'https://www.linkedin.com/in/dmitry-grankin/'
slug: 'open-source-meeting-dashboard-clone-run-vibe-code'
summary: "The Vexa Dashboard is a full meeting app you can clone and run in minutes. Built with Next.js, it includes transcription viewing, bot control, and API tutorial mode. Self-host it, extend it, or use the hosted version at vexa.ai."
---

Most meeting tools are closed-source black boxes. You can't see how they work, can't customize them, and definitely can't self-host them. The Vexa Dashboard is different — it's a thin Next.js UI over the Vexa API, fully open source under Apache 2.0.

This article walks through what the dashboard does, how to get it running locally, and why "vibe coding" on top of an open meeting platform is a better way to build.

## What the Vexa Dashboard does

The dashboard is a complete meeting application:

- **Transcription viewer** — real-time and post-meeting transcripts with speaker diarization and timestamps
- **Bot control panel** — send bots to Google Meet, Microsoft Teams, or Zoom with one click
- **API tutorial mode** — interactive walkthrough showing the actual API requests behind every UI action
- **Meeting history** — browse past meetings, search transcripts, view recordings

It's built with Next.js App Router, React Server Components, and Tailwind CSS. The entire codebase is straightforward enough to read through in an afternoon.

## Getting started in 3 minutes

```bash
# Clone the repository
git clone https://github.com/Vexa-ai/vexa-webapp.git

# Navigate into the project
cd vexa-webapp

# Install dependencies
npm install

# Start the development server
npm run dev
```

Open `http://localhost:3000`. That's it.

By default, the dashboard connects to the Vexa cloud API at `api.vexa.ai`. If you're running a self-hosted Vexa backend, point the environment variable to your own instance:

```bash
# .env.local
NEXT_PUBLIC_API_URL=https://your-vexa-instance.com
```

## Why self-host a meeting dashboard?

Three reasons developers self-host:

**Data sovereignty.** Meeting transcripts contain sensitive data. When you self-host, transcripts never leave your infrastructure. This matters for GDPR, HIPAA, and any organization that takes data residency seriously.

**Customization.** Need a custom view for your sales team? Want to pipe transcripts into your internal tools? With source code access, you modify the UI directly instead of waiting for feature requests.

**No vendor lock-in.** Apache 2.0 means you own your deployment. If Vexa the company disappeared tomorrow, your meeting infrastructure keeps running.

## The "vibe code" approach

The dashboard is intentionally thin. It's a UI layer over a well-documented REST API — not a monolithic application with business logic baked into the frontend.

This makes it ideal for rapid prototyping:

1. **Want a Slack integration?** Add a webhook handler that fires when a meeting ends
2. **Need custom analytics?** Query the API for meeting data and build your own dashboard panels
3. **Building an AI assistant?** Use the MCP server to give Claude or any AI agent direct access to meeting transcripts

The API does the heavy lifting. The dashboard shows you how to use it. You take it from there.

## Hosted vs self-hosted

You don't have to choose one or the other:

| | Hosted (vexa.ai) | Self-hosted |
|---|---|---|
| Setup | Zero — sign up and go | `git clone` + `npm run dev` |
| Infrastructure | Managed by Vexa | Your servers |
| Data location | Vexa cloud (US/EU) | Your infrastructure |
| Customization | Use as-is | Full source code access |
| Cost | From $12/mo or $0.45/hr | Free (Apache 2.0) |
| Updates | Automatic | Pull from GitHub |

Most teams start with the hosted version to evaluate, then self-host when they need customization or data sovereignty.

## Tech stack

For developers evaluating the codebase:

- **Framework:** Next.js 14 with App Router
- **Language:** TypeScript
- **Styling:** Tailwind CSS
- **Auth:** NextAuth.js
- **State:** React Server Components + client hooks
- **API client:** Fetch with typed responses

No heavy abstractions, no custom frameworks, no magic. Standard tools, standard patterns.

## Try it

**Hosted:** Go to [vexa.ai/get-started](/get-started) and send a bot to a meeting in 60 seconds.

**Self-hosted:** Clone from [GitHub](https://github.com/Vexa-ai/vexa-webapp) and run locally.

**Learn more:** Read the [API documentation](https://docs.vexa.ai) for the full reference.

The meeting infrastructure space has been dominated by closed-source vendors for too long. We think developers should be able to see, modify, and own the tools they depend on. The Vexa Dashboard is our contribution to making that possible.
