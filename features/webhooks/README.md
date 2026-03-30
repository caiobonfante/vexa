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

- **Bot status change**: fired by meeting-api when a bot joins, leaves, errors, etc. (ported to meeting-api in Phase 4 refactoring)
- **Transcript ready**: fired by meeting-api collector when transcription completes

### Data flow

```
meeting-api → HTTP POST → external URL (bot status events)
meeting-api (collector) → HTTP POST → external URL (transcript ready events)
```

### Key behaviors

- Webhook URL is configured per user via PUT /user/webhook
- Payload schema is defined in meeting-api (webhook_delivery module, moving from shared-models)
- Webhooks are fire-and-forget (no retry on failure by default)
- Webhook payloads include event type, timestamp, and event-specific data

### Data stages

| Stage | Contents | Produced by | Consumed by |
|-------|----------|-------------|-------------|
| **raw** | Trigger events (bot status change, transcript ready) | meeting-api | Webhook dispatcher |
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

### Known issues

1. **3 different payload formats** -- `event_type` vs `event` vs no field at all across different sources
2. **Test signing differs from production** -- test: `hmac(payload)`, prod: `hmac(timestamp.payload)`
3. **Internal data leaks** -- `bot_container_id`, raw `meeting.data` JSONB in payloads
4. **No event ID** -- payloads lack unique ID for idempotency
5. **Delivery log is JSONB array** -- capped at 100, stored in `user.data`, not queryable
6. **Docs don't match reality** -- `webhooks.mdx` shows 2 events, reality has 4+
7. No retry mechanism -- failed deliveries are lost

### Payload inconsistencies (3 formats today)

| Source | Field name | Shape |
|--------|-----------|-------|
| `send_status_webhook.py` | `event_type` | `{event_type, meeting, status_change}` |
| `bot_exit_tasks/send_webhook.py` | (none) | Flat meeting object, no event field |
| `post_meeting_hooks.py` | `event` | `{event, meeting}` |
| Dashboard test | `event` | `{event, data}` |

### Key code locations

| Component | Location |
|-----------|----------|
| Webhook delivery | `packages/meeting-api/meeting_api/webhook_delivery.py` (moved from shared-models) |
| Webhook config | `services/admin-api/main.py:140-192` (PUT /user/webhook) |
| Gateway proxy | `services/api-gateway/main.py:789` |
| Dashboard UI | `services/dashboard/app/webhooks/page.tsx` |
