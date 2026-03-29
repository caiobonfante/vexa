# Mission: Webhooks End-to-End Test

Focus: webhooks
Problem: Confidence is 0 after architecture refactoring. Prior findings are stale — need fresh E2E verification.
Target: webhook receiver gets delivery with P0 envelope (event_id, event_type, api_version, created_at, data) and signing headers
Stop-when: target met OR hard blocker identified with diagnosis

## Goal
Validate that webhooks actually fire and deliver correct payloads to an external receiver when bot status changes. Confidence starts at 0 — prior findings are stale (architecture refactoring reset everything).

## Context
- Feature: `features/webhooks/`
- Research done: `features/webhooks/RESEARCH.md` (2026-03-23)
- P0 spec: `features/webhooks/tests/spec-p0.md`
- Test scripts: `features/webhooks/tests/`
- Prior findings claimed 80-90 confidence but **are not trusted** — verify from scratch

## Services
- Gateway: http://localhost:8066
- Admin API: http://localhost:8067 (token: `vexa-admin-token`, header: `X-Admin-API-Key`)
- Bot manager: http://localhost:8070
- Postgres: localhost:5458
- Redis: localhost:6389
- User 5 has bot token: `vxa_bot_ycw7ssQRcEUMWyvOgz7Vie0rjfPsNJR7FfR5xmmI`

## DoD

### 1. Webhook receiver gets a delivery
- Start `webhook-receiver.sh` on host
- Configure webhook URL for user 5 (via admin API, bypassing SSRF for local testing)
- Trigger a bot status change (create a bot with fake meeting ID)
- **Receiver logs at least 1 webhook POST** within 30s
- Evidence: `results/received-webhooks.jsonl` has content

### 2. Payload matches P0 envelope spec
- Received payload has ALL of: `event_id`, `event_type`, `api_version`, `created_at`, `data`
- `event_id` starts with `evt_`
- `data` is an object (not flat meeting fields at top level)
- No `bot_container_id` in payload
- No `webhook_delivery` / `webhook_secret` in payload

### 3. Signing headers present and correct
- `X-Webhook-Signature` header present
- `X-Webhook-Timestamp` header present

## Stop-when
All 3 DoD items pass with live evidence OR hard blocker identified with diagnosis.

## Constraints
- Don't trust prior findings — verify everything from scratch
- Use the existing test scripts in `features/webhooks/tests/`
- If SSRF blocks local delivery, find the Docker gateway IP and use that
- If P0 envelope changes weren't actually applied, that's the finding — report what the actual payload looks like
