# Chat

> **Confidence: 0** — Code complete (~700 LOC), **not E2E tested.** Full stack implementation exists but has never been validated in a live meeting.
> **Tested:** Nothing end-to-end. Components exist: DOM observer, message injection, Redis relay, API endpoints.
> **Not tested:** Send message → appears in meeting chat, read messages from other participants, cross-platform behavior.
> **Contributions welcome:** E2E test in live meeting, Teams chat delivery bug ([#133](https://github.com/Vexa-ai/vexa/issues/133)).

## Why

Bidirectional meeting chat: bot reads what participants type and responds in the same chat window. Enables in-meeting AI interaction — participant asks a question in Teams chat, agent processes it, bot responds in chat.

**Architecture note:** In-meeting chat, Telegram, web dashboard, and future Slack/Discord all flow through the same Agent API. Same agent, same workspace, regardless of surface.

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
