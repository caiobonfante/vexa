# Webhooks Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules
> Development cycle: [features/README.md](../../README.md#spec-driven-features) — research, spec, build & test

## Mission

Build production-grade webhook delivery. Consistent payloads, reliable delivery, granular events, great developer experience. Recall.ai is the benchmark.

## Development cycle

This is a **spec-driven feature** — see [features/README.md](../../README.md#spec-driven-features).

```
RESEARCH (done)              SPEC                        BUILD & TEST
─────────────                ────                        ────────────
RESEARCH.md exists           Pick priority batch         Implement spec item
Gaps identified              Write payload schemas       make receiver (terminal 1)
Priorities ranked            Write test assertions       make test (terminal 2)
                             Tests should FAIL           Check received payloads
                                                         Update findings.md
```

### Current stage: BUILD & TEST (P0 complete, P1 next)

**Research:** `RESEARCH.md` — 2026-03-23, competitor analysis + code audit.

**Priority batches:**

| Batch | Items | Effort |
|-------|-------|--------|
| P0-envelope | Standardize payload envelope (3 formats today → 1), add event_id, fix test signing | Days |
| P0-events | Add `transcript.ready` event | Days |
| P1-lifecycle | Add granular bot lifecycle events (joining, waiting_room, in_call, etc.) | Days |
| P1-endpoints | Multiple webhook endpoints per user, per-endpoint event filtering | Week |
| P1-infra | Proper `webhook_delivery_log` table, replay capability | Week |
| P2-realtime | Participant join/leave events, real-time transcript segments | Week |
| P2-reliability | Circuit breaker, dead letter alerting, endpoint health | Days |

### On entry: determine your stage

1. **Does `RESEARCH.md` exist?** Yes → research is done.
2. **Does `tests/spec-{batch}.md` exist for current batch?** If no → you are in SPEC.
3. **Do test assertions exist and fail?** If yes → you are in BUILD & TEST.
4. **Do all tests pass?** If yes → move to next batch or GATE.

## Scope

You own webhook delivery: event catalog, payload schemas, signing, retry, delivery tracking, endpoint management. You dispatch to service agents for backend changes.

### Gate (local)

| Check | Pass | Fail |
|-------|------|------|
| Config | PUT /user/webhook stores URL, GET reads it back | Config not persisted |
| Bot status fires | Bot status change triggers webhook delivery | No webhook received |
| Envelope | All events use same shape: `{event_id, event_type, api_version, created_at, data}` | Inconsistent field names |
| Signing | `X-Webhook-Signature` + `X-Webhook-Timestamp` present and verifiable | Missing headers or wrong HMAC |
| Test matches prod | Test webhook uses same signing as production | Different signing schemes |
| Retry | Failed delivery retried per backoff schedule | Dropped silently |
| Payload quality | No internal data leaks (container IDs, raw JSONB) | Internal fields exposed |

### Docs

- [Webhooks](../../docs/webhooks.mdx)
- [Local Webhook Development](../../docs/local-webhook-development.mdx)

### Edges

**Crosses:**
- shared-models (`webhook_delivery.py`, `webhook_retry_worker.py`, `webhook_url.py`) — delivery, retry, SSRF
- bot-manager (`tasks/send_status_webhook.py`, `tasks/bot_exit_tasks/`) — fires events
- transcription-collector — fires transcript-ready events
- admin-api (`main.py:140-192`) — PUT /user/webhook
- api-gateway (`main.py:789`) — proxies webhook config
- dashboard (`app/webhooks/page.tsx`) — webhook management UI

**Payload inconsistencies found (3 formats):**

| Source | Field name | Shape |
|--------|-----------|-------|
| `send_status_webhook.py` | `event_type` | `{event_type, meeting, status_change}` |
| `bot_exit_tasks/send_webhook.py` | (none) | Flat meeting object, no event field |
| `post_meeting_hooks.py` | `event` | `{event, meeting}` |
| Dashboard test | `event` | `{event, data}` |

### Counterparts
- Service agents: `services/bot-manager`, `services/transcription-collector`, `services/admin-api`
- Lib agents: `libs/shared-models`
- Related features: mcp-integration (agent-driven complement to webhooks)

## How to test

```bash
cd features/webhooks/tests

# Terminal 1: start receiver
make receiver

# Terminal 2: run tests
cp ../.env.example ../.env   # fill in values
make smoke                    # configure URL
make test                     # all tests
```

Receiver logs to `results/received-webhooks.jsonl`. Bots run in Docker, so webhook URL uses `host.docker.internal` to reach host.

## Known issues (from research)

1. **3 different payload formats** — `event_type` vs `event` vs no field at all
2. **Test signing differs from production** — test: `hmac(payload)`, prod: `hmac(timestamp.payload)`
3. **Internal data leaks** — `bot_container_id`, raw `meeting.data` JSONB in payloads
4. **No event ID** — payloads lack unique ID for idempotency
5. **Delivery log is JSONB array** — capped at 100, stored in `user.data`, not queryable
6. **Docs don't match reality** — `webhooks.mdx` shows 2 events, reality has 4+

## Critical findings
Save to `tests/findings.md`.
