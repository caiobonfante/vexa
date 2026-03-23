# Webhooks Research (2026-03-23)

Research from competitor analysis (Recall.ai, Fireflies, Otter, AssemblyAI), industry best practices, and deep code audit.

## Current State

4 event types, HMAC-SHA256 signing, Redis retry queue, dashboard UI with delivery history.

### Events

| Event | Default | Trigger |
|-------|---------|---------|
| `meeting.completed` | ON | Meeting ends |
| `meeting.started` | OFF | Bot admitted |
| `bot.failed` | OFF | Bot fails |
| `recording.completed` | Always | Recording upload done |

### Delivery

- HMAC-SHA256 signing (`X-Webhook-Signature`, `X-Webhook-Timestamp`)
- 30s timeout, 3 in-process retries
- Durable retry via Redis: 1m, 5m, 30m, 2h backoff; 24h max age
- SSRF protection (blocks private IPs, metadata endpoints)
- Delivery status in `meeting.data.webhook_delivery` JSONB

### Configuration

- Single URL per user (`user.data.webhook_url`)
- Single secret per user (`user.data.webhook_secret`)
- Per-event toggles in `user.data.webhook_events`
- Dashboard at `/webhooks` with test button, delivery history, stats

---

## Competitor Comparison

### Recall.ai (closest competitor — uses Svix)

- **~15+ event types** including 9 granular bot lifecycle events (`bot.joining_call`, `bot.in_waiting_room`, `bot.recording_permission_allowed/denied`, etc.)
- **Real-time events**: `transcript.data` (per utterance), `participant.joined/left`, `participant.speech_on/off`, `participant.screenshare_on/off`, `participant.chat_message`
- **Per-bot real-time endpoints** (URL + event list specified at bot creation time)
- **Multiple webhook endpoints** with independent event subscriptions
- **Svix-powered dashboard** with message history, failure tracking, replay
- **8 retry attempts** over ~33 hours (vs Vexa's 4 over ~2.5 hours)
- Auto-disable after 5 days of failures
- Regional dashboards (US, EU, Japan)

### Fireflies.ai
- Single event: "Transcription completed"
- Minimal payload (meetingId only — requires API call for data)
- SHA-256 HMAC signature

### Otter.ai
- Events: `Conversation.processed`, `Conversation.shared`
- Rich payload: includes full transcript, summary, action items, insights
- Enterprise-only

### AssemblyAI
- Custom auth header (name + value configurable)
- Fixed source IP for firewall allow-listing

---

## Critical Issues Found

### 1. Inconsistent payload shapes (3 different formats)

| Source file | Field name | Shape |
|-------------|-----------|-------|
| `send_status_webhook.py` | `event_type` | `{"event_type": "...", "meeting": {...}, "status_change": {...}}` |
| `send_webhook.py` (post-meeting) | (none) | Flat meeting object at top level, no event_type |
| `post_meeting_hooks.py` | `event` | `{"event": "meeting.completed", "meeting": {...}}` |
| Dashboard test | `event` | `{"event": "test", "data": {...}}` |

Three different field names (`event`, `event_type`, none) across four code paths.

### 2. Test webhook signs differently from production

- Dashboard test: `crypto.createHmac("sha256", secret).update(payloadStr)` (payload only)
- Production: `hmac(timestamp.payload)` with `X-Webhook-Timestamp`

Developers verifying signatures with the test webhook get different behavior than production.

### 3. Internal data leaks in payloads

- `bot_container_id` (Docker container ID) exposed
- `meeting.data` JSONB bag included raw — leaks `webhook_delivery` status, internal metadata

### 4. No event ID for idempotency

Payloads lack a unique `event_id`. Consumers cannot deduplicate retried deliveries.

### 5. Docs don't match reality

- `webhooks.mdx` documents only `meeting.status_change` and `recording.completed`
- Doesn't mention `meeting.completed`, `meeting.started`, `bot.failed`
- Doesn't document `X-Webhook-Signature` / `X-Webhook-Timestamp` headers
- No signature verification code samples

---

## Missing Events (prioritized)

| Priority | Event | Rationale |
|----------|-------|-----------|
| **P0** | `transcript.ready` | Most requested event for a meeting bot platform. Currently no transcript webhook exists despite README mentioning it. |
| **P0** | `bot.joining` / `bot.waiting_room` / `bot.admitted` | Recall has 9 granular lifecycle events. Vexa collapses everything into `meeting.started`. Integrators need lobby/admission status. |
| **P1** | `participant.joined` / `participant.left` | Essential for CRM integrations, attendance tracking. Bot already sees this data. |
| **P1** | `transcript.segment` (real-time) | Recall fires `transcript.data` per utterance. Enables live transcript UIs without WebSocket. |
| **P1** | `recording.started` / `recording.failed` | Only `recording.completed` exists. No notification on failure. |
| **P2** | `bot.error_detail` | `bot.failed` exists but lacks structured error info (code, stage, recovery suggestion). |
| **P2** | `meeting.metadata_updated` | Title detected, participant list changed. |

---

## Missing Features (prioritized)

| Priority | Feature | Rationale |
|----------|---------|-----------|
| **P0** | Multiple webhook endpoints | Vexa: 1 URL per user. Recall: multiple with independent event subscriptions. Table-stakes. |
| **P0** | Standardized payload envelope | Fix the 3 different formats. Use: `{"event_id", "event_type", "api_version", "created_at", "data"}` everywhere. |
| **P1** | Per-endpoint event filtering | With multiple endpoints, each needs its own event set. |
| **P1** | Per-bot webhook URL | Recall allows specifying webhook URL + events when creating a bot. Powerful for multi-tenant. |
| **P1** | Webhook replay | Dashboard shows history but can't re-send. Recall (Svix) supports this. |
| **P1** | Proper delivery log table | Currently JSONB array capped at 100 in `user.data`. Need a `webhook_delivery_log` table. |
| **P2** | Circuit breaker | Auto-disable after sustained failures (Recall: 5 days). Prevents wasted resources. |
| **P2** | Dead letter queue alerting | Redis retry drops events after 24h silently. Should alert. |
| **P2** | Webhook versioning | No `api_version` field. No way to evolve schemas safely. |
| **P3** | Rate limiting / backpressure | No per-endpoint rate limiting. Burst events could overwhelm consumer. |
| **P3** | Fixed source IP | AssemblyAI publishes source IPs for firewall rules. Enterprise need. |

---

## Developer Experience Gaps

1. **No webhook event catalog** — docs page shows 2 events, reality has 4+
2. **Signature verification undocumented** — HMAC scheme exists but not described for consumers
3. **No verification code samples** — Stripe/Recall provide copy-paste snippets in Python/Node/Go
4. **Test payload differs from real payloads** — can't validate parsing with test webhook
5. **No payload inspection in dashboard** — delivery history shows status but not what was sent
6. **No OpenAPI/JSON Schema for payloads** — no machine-readable spec

---

## Recommendations

### P0 — Foundation (do first, everything else depends on this)

1. **Standardize the webhook envelope** — single shape for all events:
   ```json
   {
     "event_id": "evt_abc123",
     "event_type": "meeting.completed",
     "api_version": "2026-03-01",
     "created_at": "2026-03-23T20:10:12Z",
     "data": { ... }
   }
   ```
   Fix the three different field names. Add unique event IDs for idempotency.

2. **Add `transcript.ready` event** — most requested event. Include transcript text or summary in payload so consumers don't need a follow-up API call.

3. **Fix signature verification** — align test signing with production signing. Document the scheme. Provide verification code samples.

### P1 — Core Features

4. **Add granular bot lifecycle events** — `bot.joining`, `bot.waiting_room`, `bot.in_call`, `bot.recording`, `bot.leaving`, `bot.done`, `bot.fatal`. These map to existing status transitions in bot-manager.

5. **Support multiple webhook endpoints** — move from `user.data.webhook_url` to a `webhook_endpoints` table. Each endpoint gets its own URL, secret, event filter, active/disabled status.

6. **Move delivery logs to proper DB table** — replace the JSONB array (capped at 100) with a `webhook_delivery_log` table. Enables replay, proper querying, and the delivery dashboard.

7. **Add webhook replay** — "Retry" button in dashboard + `POST /webhooks/deliveries/{id}/retry` API endpoint.

### P2 — Polish

8. **Add participant join/leave events** — bot already sees this data via caption/DOM observer.

9. **Stop leaking internal data** — remove `bot_container_id`, filter `meeting.data` to exclude internal fields.

10. **Add circuit breaker** — auto-disable after sustained failures, surface health in dashboard.

---

## Sources

- [Recall.ai Webhooks](https://docs.recall.ai/docs/bot-status-change-events)
- [Recall.ai Real-Time Endpoints](https://docs.recall.ai/docs/real-time-webhook-endpoints)
- [Recall.ai + Svix](https://www.svix.com/customers/recall-ai/)
- [Fireflies.ai Webhooks](https://docs.fireflies.ai/graphql-api/webhooks)
- [Otter.ai Webhooks](https://help.otter.ai/hc/en-us/articles/35634832371735-Workspace-Webhooks)
- [AssemblyAI Webhooks](https://www.assemblyai.com/docs/deployment/webhooks)
- [Hookdeck: Building Reliable Outbound Webhooks](https://hookdeck.com/blog/building-reliable-outbound-webhooks)
- [Svix: Webhooks as a Service](https://www.svix.com/)
