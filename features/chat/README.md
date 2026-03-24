# Chat

> **Confidence: 0** — Code complete (~700 LOC), **not E2E tested.** Full stack implementation exists but has never been validated in a live meeting.
> **Tested:** Nothing end-to-end. Components exist: DOM observer, message injection, Redis relay, API endpoints.
> **Not tested:** Send message → appears in meeting chat, read messages from other participants, cross-platform behavior.
> **Contributions welcome:** E2E test in live meeting, Teams chat delivery bug ([#133](https://github.com/Vexa-ai/vexa/issues/133)).

## Why

Meetings have two communication channels — voice and chat. The speaking bot covers voice. This feature covers chat: the bot reads what participants type and responds in the same chat window.

**In-meeting AI interaction:** A participant types "What were the action items from last week?" in the Teams chat. The bot reads it, the agent processes it against stored transcripts, and the bot responds in chat — all during the live meeting, no app-switching.

**Same backbone, every surface:** In-meeting chat, Telegram, web dashboard, and future Slack/Discord all flow through the same Agent API. The agent doesn't know or care which surface the message came from — it processes and responds the same way. A message from Telegram ("join my 2pm meeting") and a message from the meeting chat ("summarize what we discussed") hit the same agent, same workspace, same memory.

| Surface | How it reaches the agent | Status |
|---------|------------------------|--------|
| **Meeting chat** (this feature) | Bot DOM observer → Redis → Agent API | Code complete |
| **Web dashboard** | WebSocket → Agent API | Working |
| **Telegram** | Telegram Bot → Agent API | Working |
| **Slack/Discord** (future) | Bot → Agent API | Planned |

**Your agent, wherever you are:** Message it from your phone on Telegram while commuting. Message it from the meeting chat during a call. Message it from the dashboard at your desk. Same agent, same memory, same context.

## What

This feature enables the bot to observe meeting chat messages and inject messages into the meeting chat via API.

### Documentation
- [Interactive Bots](../../docs/interactive-bots.mdx)
- [Interactive Bots API](../../docs/api/interactive-bots.mdx)

### Components

- **vexa-bot**: observes the meeting chat DOM for new messages, injects messages into the DOM
- **bot-manager**: relays chat commands between API and bot
- **api-gateway**: exposes chat endpoints (POST to send, GET to read)

### Data flow

```
Sending:  client → api-gateway → bot-manager → vexa-bot → meeting chat DOM
Reading:  meeting chat DOM → vexa-bot → Redis → api-gateway → client
```

### Key behaviors

- POST /bots/{id}/chat sends a message into the meeting chat
- GET /bots/{id}/chat returns messages observed from other participants
- Bot observes the DOM for new chat messages in real-time
- Messages are relayed via bot-manager and Redis
- Chat works across supported meeting platforms

### Data stages

| Stage | Contents | Produced by | Consumed by |
|-------|----------|-------------|-------------|
| **raw** | Chat messages from meeting DOM (timestamped) | Live meeting capture | Validation, replay |
| **rendered** | API responses (GET /bots/{id}/chat) | api-gateway | Clients |

No collected datasets yet. When testing matures, capture raw chat DOM events + API responses during live meetings.

## How

This is a cross-service feature. Testing requires the full compose stack with a mock meeting.

### Verify

1. Start the compose stack: `make all` (from `deploy/compose/`)
2. Start a bot in a mock meeting
3. Send a message: `POST /bots/{id}/chat` with `{"message": "Hello"}`
4. Verify the message appears in the meeting chat
5. Have another participant send a chat message
6. Read messages: `GET /bots/{id}/chat` — verify the participant's message appears

### Known limitations

- Chat observation depends on platform-specific DOM structure
- No message history persistence beyond the meeting session
- Rate limiting on chat injection not documented
