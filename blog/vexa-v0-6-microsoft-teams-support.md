---
title: 'Vexa v0.6 — The Open-Source Meeting API, now with Microsoft Teams'
date: '2025-10-06'
author: 'Dmitry Grankin'
authorImage: '/dmitry-grankin.jpg'
authorLinkedIn: 'https://www.linkedin.com/in/dmitry-grankin/'
heroImage: '/assets/v06_msteams.png'
slug: 'vexa-v0-6-microsoft-teams-support'
summary: "Open-source meeting API with Microsoft Teams and Google Meet. Real-time WebSocket streaming, MCP server for agents. Hosted and self-hosted: same APIs, no lock-in."
---
## AI is hungry for data. Vexa delivers.

Vexa v0.6 is how developers and enterprises access real-time meeting data from Microsoft Teams and Google Meet. Build agents, automations, and applications that listen and act on live conversations.

Start hosted, go self-hosted when you're ready. Same APIs, zero rewrites. 
Your transcripts stay in your house—not someone else's cloud.

---

## What's new in v0.6

- **Microsoft Teams support**: Send a bot to any Teams meeting from a share link (similar to Google Meet). Cross-platform coverage with Google Meet in one API.
- **Real-time WebSocket streaming**: The fastest way to receive transcripts for immediate agent reactions and live integrations.
- **MCP server for agents**: Connect Claude, Cursor, Windserf, and other MCP-enabled agents to Vexa directly—no custom glue code.
- **Production hardening**: Reliability upgrades from a month of operating our hosted service in the wild.

---

## Why it matters

- **Interchangeability**: Start hosted for speed, migrate to self-hosted for control. Same APIs. No lock-in.
- **Data sovereignty**: Keep meeting data inside your infrastructure when you need to. Compliance without compromises.
- **Developer speed**: REST + WebSocket APIs, simple auth, and examples that get you from idea to production fast.
- **Enterprise reliability**: Battle-tested in multi-user, multi-tenant environments.

---

## Key features at a glance

- **Platforms**: Microsoft Teams + Google Meet transcription API
- **Streaming**: WebSocket real-time delivery for sub-second reactions
- **Agents**: MCP server support (Claude, GPT, and others)
- **APIs**: REST + WebSocket for flexible integration
- **Deployment**: Hosted and self-hosted with identical APIs
- **Reliability**: Production-hardened connection + error handling
- **Open Source**: Apache-2.0 licensed


---

## Getting started

### Hosted (fastest path)

1. Create an API key: [vexa.ai/dashboard/api-keys](https://vexa.ai/dashboard/api-keys)
2. Start a bot and stream transcripts in minutes

### Self-hosted (full control)

```bash
git clone https://github.com/Vexa-ai/vexa.git
cd vexa
make all            # CPU default (Whisper tiny) — great for dev
# For GPU:
# make all TARGET=gpu    # (Whisper medium) — recommended for production quality
```

---

## API examples

### Start a Teams transcription bot

```bash
curl -X POST https://api.cloud.vexa.ai/bots \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <API_KEY>" \
  -d '{
    "platform": "teams",
    "native_meeting_id": "<NUMERIC_MEETING_ID>",
    "passcode": "<MEETING_PASSCODE>"
  }'
```

### Start a Google Meet transcription bot

```bash
curl -X POST https://api.cloud.vexa.ai/bots \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <API_KEY>" \
  -d '{
    "platform": "google_meet",
    "native_meeting_id": "<MEET_CODE_XXX-XXXX-XXX>"
  }'
```

### Stream transcripts in real time (WebSocket)

Once a bot joins your meeting, connect to the WebSocket endpoint to receive streaming transcript segments for immediate processing. See documentation for message shapes and event types.

- Docs: [WebSocket streaming guide](https://github.com/Vexa-ai/vexa/blob/main/docs/websocket.mdx)

---

## Agents love MCP

MCP-enabled agents can talk to Vexa without custom API calls. Point your agent at Vexa's MCP server to fetch transcripts, start bots, and manage meetings.

- Docs: [MCP setup](https://vexa.ai/blog/claude-desktop-vexa-mcp-google-meet-transcripts)

---

## Built for developers, ready for enterprises

### For developers

- Real-time streaming for instant agent reactions
- Simple, predictable API surface (REST + WebSocket)
- Examples for popular stacks and automation tools

### For enterprises

- Self-hosted deployment keeps data in your environment
- Interchangeable hosted ↔ self-hosted with zero rewrites
- Horizontal scalability and operational visibility

---

## FAQ (short and useful)

**Does Vexa support Microsoft Teams and Google Meet?**
Yes. v0.6 supports both, using one API and a consistent streaming model.

**How do I get real-time transcripts?**
Use the WebSocket streaming API. It delivers transcript segments as they are generated for sub-second reactions.

**Can I switch between hosted and self-hosted?**
Absolutely. Start hosted, migrate to self-hosted when ready. Same APIs, no vendor lock-in.

**Is Vexa open source?**
Yes. Apache-2.0 licensed. You can self-host the entire stack.

**Is it ready for production?**
Yes. v0.6 includes reliability improvements from running the hosted service in real-world multi-tenant environments.

**Do you support MCP for agents?**
Yes. Agents using the Model Context Protocol can connect to Vexa directly.

---

## Join the community

- 🌐 [Get started at vexa.ai](https://vexa.ai)
- 💬 [Join our Discord](https://discord.gg/Ga9duGkVz9)
- ⭐ [Star on GitHub](https://github.com/Vexa-ai/vexa)
- 📖 [Read the documentation](https://github.com/Vexa-ai/vexa/blob/main/docs/user_api_guide.mdx)
- 🚀 [Try the hosted API](https://vexa.ai/dashboard/api-keys)
