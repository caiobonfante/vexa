# Webhooks

> **Confidence: 0** — RESET after architecture refactoring. webhook_delivery.py moved to meeting-api. Webhook URL now read from meeting.data (was User.data). All delivery paths changed.
> **Tested:** Payload envelope consistency, event_id generation, signing (timestamp.payload HMAC), bot status events fire.
> **Not tested:** Delivery to public URLs (tested only with localhost), retry mechanism (fire-and-forget today), transcript.ready event.
> **Contributions welcome:** Retry via scheduler (migrate webhook_retry_worker), circuit breaker, dead letter alerting.

## Why

Push event notifications to external endpoints without polling. Events: `meeting.completed`, `transcript.ready`, `bot.error`, bot status changes. Combined with the scheduler's `on_success`/`on_failure` callbacks, webhooks are the trigger layer for post-meeting automation pipelines.

## What

This feature fires HTTP POST requests to user-configured URLs when bot status changes or transcripts become ready.

### Documentation
- [Webhooks](../../docs/webhooks.mdx)
- [Local Webhook Development](../../docs/local-webhook-development.mdx)

### Event types

- **Bot status change**: fired by bot-manager when a bot joins, leaves, errors, etc.
- **Transcript ready**: fired by transcription-collector when transcription completes

### Data flow

```
bot-manager → HTTP POST → external URL (bot status events)
transcription-collector → HTTP POST → external URL (transcript ready events)
```

### Key behaviors

- Webhook URL is configured per user via PUT /user/webhook
- Payload schema is defined in shared-models
- Webhooks are fire-and-forget (no retry on failure by default)
- Webhook payloads include event type, timestamp, and event-specific data

### Data stages

| Stage | Contents | Produced by | Consumed by |
|-------|----------|-------------|-------------|
| **raw** | Trigger events (bot status change, transcript ready) | bot-manager, collector | Webhook dispatcher |
| **rendered** | HTTP POST payloads delivered to external URLs | Webhook dispatcher | External endpoints |

No collected datasets yet. Capture trigger event + delivered payload pairs for regression testing.

## How

This is a cross-service feature. Testing requires the full compose stack plus a webhook receiver.

### Verify

1. Start the compose stack: `make all` (from `deploy/compose/`)
2. Start a webhook receiver: `python -m http.server 9999` or use webhook.site
3. Configure webhook: `PUT /user/webhook` with the receiver URL
4. Trigger a bot status change (start/stop a bot)
5. Verify the receiver got the correct payload

### Known limitations

- No retry mechanism — failed deliveries are lost
- No webhook signature verification for authenticity
