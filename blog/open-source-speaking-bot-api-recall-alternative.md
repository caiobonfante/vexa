---
title: 'Open-Source Speaking Bot API: Make Your Meeting Bot Talk (Recall.ai Output Media Alternative)'
date: '2026-03-24'
author: 'Dmitry Grankin'
authorImage: '/dmitry-grankin.jpg'
authorLinkedIn: 'https://www.linkedin.com/in/dmitry-grankin/'
heroImage: '/assets/speaking-bot-api.png'
slug: 'open-source-speaking-bot-api-recall-alternative'
summary: "Recall.ai just launched their Output Media API — bots that talk in meetings. Vexa has had this open-source since v0.9. Here's how to build interactive meeting bots that speak, chat, and share screens."
---

Meeting bots that only listen are table stakes. The next step: bots that **participate** — answering questions verbally, posting to chat, sharing their screen.

[Recall.ai launched their Output Media API](https://www.ycombinator.com/launches/M9k-recall-ai-output-media-api-ai-agents-that-talk-in-meetings) — bots that talk in meetings. It's a closed, paid API.

Vexa has the same capability — open-source, self-hosted, and controllable via MCP so your AI agent (Claude, Cursor) can speak in meetings with a tool call.

---

## What interactive bots can do

| Capability | API | How it works |
|-----------|-----|-------------|
| **Speak** | `POST /bots/{id}/speak` | Text → TTS service → PulseAudio → meeting audio |
| **Chat** | `POST /bots/{id}/chat` | Message injected into meeting chat DOM |
| **Read chat** | `GET /bots/{id}/chat` | DOM observer captures participant messages |
| **Share screen** | `POST /bots/{id}/screen` | URL rendered in bot's browser, shared to meeting |
| **Set avatar** | `POST /bots/{id}/avatar` | Custom display image for the bot |

All while simultaneously transcribing the meeting in real-time.

## Use cases beyond "read a summary"

| Use case | How |
|----------|-----|
| **AI facilitator** | Bot tracks agenda, announces time checks, prompts quiet participants to share updates |
| **Real-time translator** | Bot transcribes in English, speaks translation in Spanish for remote team members |
| **Sales coach** | Bot listens to customer objections, whispers suggested responses via chat |
| **Standup bot** | Bot reads yesterday's action items aloud, asks each person for their update |
| **Q&A responder** | Participant types question in chat → agent processes → bot responds in chat or speaks the answer |

## MCP integration

Your AI agent can control the bot through MCP tool calls:

```
Agent (via MCP): bot_speak("Here are the three action items from today's discussion...")
Agent (via MCP): send_chat("Reminder: next sync is Thursday 2pm")
Agent (via MCP): share_screen("https://dashboard.internal/metrics")
```

Otter's MCP server is read-only. Fireflies' MCP server is read-heavy. Vexa's MCP server is the only one where agents can **actively participate** in meetings — read + write + control + speak.

## Quick start

```bash
# Send bot to meeting
curl -X POST "$API_BASE/bots" \
  -H "X-API-Key: $API_KEY" \
  -d '{"platform": "teams", "native_meeting_id": "123", "passcode": "abc"}'

# Make it speak
curl -X POST "$API_BASE/bots/$BOT_ID/speak" \
  -H "X-API-Key: $API_KEY" \
  -d '{"text": "Good morning everyone. Here are the action items from last week."}'

# Send a chat message
curl -X POST "$API_BASE/bots/$BOT_ID/chat" \
  -H "X-API-Key: $API_KEY" \
  -d '{"message": "Meeting summary will be posted to #engineering after this call."}'
```

## Vexa vs Recall.ai Output Media API

| | Recall.ai Output Media | Vexa Interactive Bots |
|---|---|---|
| **Speak in meetings** | Yes | Yes |
| **Chat in meetings** | Yes | Yes |
| **Share screen** | Yes | Yes |
| **Open source** | No | Yes (Apache 2.0) |
| **Self-hosted** | No | Yes |
| **MCP server** | No | Yes (17 tools) |
| **Pricing** | Per-minute, closed | Self-hosted: free. Hosted: from $0.45/hr |

---

**Current status:** Speaking bot is at [confidence 0](../features/speaking-bot/) — code complete but not E2E tested. TTS pipeline and PulseAudio integration exist. This is a high-impact contribution area: the first person to run an E2E test (speak command → participants hear audio) moves confidence from 0 to 80+. See the [feature README](../features/speaking-bot/) for details.
