# Webhooks Tests

## Testing approach

Webhooks are an **event-driven, fire-and-forget** feature. Testing requires a local receiver to capture delivered payloads, plus trigger events (bot status changes) that fire webhooks.

### Test types

| Test | What it validates | Needs |
|------|------------------|-------|
| `make smoke` | Configure webhook URL via PUT | api-gateway, admin-api |
| `make test-config` | Set and clear webhook URL | api-gateway, admin-api |
| `make test-bot-status` | Bot status change fires webhook to receiver | full stack + receiver |
| `make test-payload` | Validate received webhook payload schema | received webhooks |

### How to run

```bash
cd features/webhooks/tests

# Setup
cp ../.env.example ../.env  # fill in values

# Terminal 1: start the receiver
make receiver

# Terminal 2: run tests
make smoke           # quick check
make test            # all tests
```

### Webhook receiver

`make receiver` starts a Python HTTP server that logs all incoming POSTs to `results/received-webhooks.jsonl`. Each entry includes timestamp, path, headers, and parsed JSON body.

The receiver must be running before `test-bot-status` — otherwise there's nothing to catch the webhook.

Note: bots run in Docker, so the webhook URL uses `host.docker.internal` to reach the receiver on the host. If your Docker setup doesn't support this, set `WEBHOOK_URL` in `.env`.

### What to look for

- PASS: PUT /user/webhook returns 200
- PASS: bot creation triggers webhook delivery to receiver
- PASS: webhook payload contains `event` and `timestamp` fields
- Check `results/received-webhooks.jsonl` for full payload details

### Recent improvements

- **#183** (2026-03-12): Durable webhook delivery — failed webhooks persist to Redis for retry
- **#184** (2026-03-12): Delivery status written to meeting record
