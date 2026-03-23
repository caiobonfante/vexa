# Validation Report — 2026-03-23

## Summary

Three features validated against live services. One fully passes, two need container rebuilds for P0 fixes.

| Feature | Tests | Pass | Fail | Skip | Status |
|---------|-------|------|------|------|--------|
| **token-scoping** | 14 | 14 | 0 | 0 | **PASS** |
| **mcp-integration** | 10 | 7 | 2 | 1 | PARTIAL (rebuild needed) |
| **webhooks** | 8 | 2 | 0 | 6 | PARTIAL (rebuild + bot lifecycle needed) |

---

## Token Scoping — PASS (14/14)

All tests pass against live services. No container rebuild needed — scope enforcement is in deployed code.

### What was tested

| Test | Result | Evidence |
|------|--------|----------|
| Create user-scoped token | PASS | Token starts with `vxa_user_` |
| Create bot-scoped token | PASS | Token starts with `vxa_bot_` |
| Create tx-scoped token | PASS | Token starts with `vxa_tx_` |
| Create admin-scoped token | PASS | Token starts with `vxa_admin_` |
| user → GET /bots/status | PASS (200) | bot-manager allows `{bot, user, admin}` |
| user → GET /meetings | PASS (200) | collector allows `{tx, user, admin}` |
| bot → GET /bots/status | PASS (200) | bot scope allowed |
| bot → GET /meetings | PASS (403) | bot scope denied by collector |
| tx → GET /bots/status | PASS (403) | tx scope denied by bot-manager |
| tx → GET /meetings | PASS (200) | tx scope allowed |
| admin → GET /bots/status | PASS (200) | admin allowed everywhere |
| admin → GET /meetings | PASS (200) | admin allowed everywhere |
| Token prefix format | PASS | All 4 prefixes verified |
| Legacy backward compat | PASS | Legacy token handled correctly |

### Command to reproduce

```bash
cd features/token-scoping/tests && make test
```

---

## MCP Integration — PARTIAL (7 pass, 2 fail, 1 skip)

Core MCP functionality works. P0 fixes (pagination + download URL) written but containers need rebuild.

### What was tested

| Test | Result | Evidence |
|------|--------|----------|
| MCP reachable via gateway | PASS | HTTP 200 |
| Session initialization | PASS | Mcp-Session-Id returned |
| 17 tools discoverable | PASS | tools/list returns all 17 |
| parse_meeting_link | PASS | Returns `google_meet` for GMeet URL |
| list_meetings returns data | PASS | 211 meetings returned |
| Invalid token rejected | PASS | Error in tool result |
| Nonexistent tool error | PASS | isError=true |
| **list_meetings limit=5** | **FAIL** | Returns 211 (code written, container not rebuilt) |
| **Recording download URL** | **FAIL** | Returns `minio:9000` (code written, container not rebuilt) |
| Recording test | SKIP | No recordings without media files |

### P0 code changes (on disk, not deployed)

1. `services/mcp/main.py` — `list_meetings` now accepts `limit`, `offset`, `status`, `platform` params
2. `services/mcp/main.py` — `get_recording_media_download` rewrites `minio:*` URLs to gateway URL
3. `services/transcription-collector/api/endpoints.py` — `get_meetings` accepts `limit`, `offset`, `status`, `platform`

### To complete validation

```bash
# Rebuild
cd deploy/compose && docker compose build mcp transcription-collector
docker compose up -d mcp transcription-collector

# Re-test
cd features/mcp-integration/tests && make test
```

---

## Webhooks — PARTIAL (config works, delivery not tested)

Configuration endpoints work. Webhook delivery could not be tested because:
1. Bot-manager container has old code (P0 envelope changes not deployed)
2. SSRF protection blocks private IPs (receiver URL must be set via admin-api bypass)
3. Bots with fake meeting URLs hang in `joining` for 60s+ instead of failing fast

### What was tested

| Test | Result | Evidence |
|------|--------|----------|
| PUT /user/webhook (public URL) | PASS (200) | Endpoint works |
| SSRF blocks private IPs | PASS (400) | Correctly rejects `host.docker.internal` |
| Webhook receiver captures POSTs | PASS | Test POST received and logged |
| Bot status triggers webhook | NOT TESTED | Bot stuck in `joining`, container has old code |
| Envelope format | NOT TESTED | Needs rebuild |
| Signing headers | NOT TESTED | Needs rebuild |
| Internal data filtering | NOT TESTED | Needs rebuild |

### P0 code changes (on disk, not deployed)

1. `libs/shared-models/shared_models/webhook_delivery.py` — `build_envelope()`, `clean_meeting_data()`
2. `services/bot-manager/app/tasks/send_status_webhook.py` — uses envelope, removes `bot_container_id`
3. `services/bot-manager/app/tasks/bot_exit_tasks/send_webhook.py` — uses envelope, wraps in `data.meeting`
4. `services/bot-manager/app/tasks/bot_exit_tasks/post_meeting_hooks.py` — uses envelope
5. `services/bot-manager/app/main.py` — `send_event_webhook()` uses envelope + `deliver()` with HMAC
6. `services/dashboard/src/app/api/webhooks/test/route.ts` — envelope format, production-aligned signing

### To complete validation

```bash
# Rebuild
cd deploy/compose && docker compose build bot-manager dashboard
docker compose up -d bot-manager dashboard

# Terminal 1: receiver
cd features/webhooks/tests && make receiver

# Terminal 2: test (needs a real meeting for bot lifecycle)
make test
```

---

## Infrastructure Notes

- Compose stack: all 15+ containers running healthy
- Ports: gateway :8066, admin-api :8067, MCP :18898, collector :8123, postgres :5448
- 4 active bots running (from other test activities)
- All code changes are on the `fix/restore-working-bot` branch, uncommitted

## Test Framework Validation

The test frameworks themselves are validated and working:

| Framework | Status | Notes |
|-----------|--------|-------|
| token-scoping `test-token-scoping.sh` | Working | Admin API key header fixed, correct endpoints |
| mcp-integration `test-mcp.sh` | Working | MCP session handling fixed, proper init flow |
| webhooks `test-webhooks.sh` | Partially working | Config tests pass, delivery needs rebuild |
| webhook-receiver.sh | Working | Captures POSTs to JSONL |

## Research Deliverables

| Deliverable | Location | Status |
|-------------|----------|--------|
| MCP ecosystem research | `features/mcp-integration/RESEARCH.md` | Complete |
| MCP live testing | MCP findings (17 tools, 4 prompts, bugs) | Complete |
| Webhook competitive analysis | `features/webhooks/RESEARCH.md` | Complete |
| Google Calendar research | Pending (background agent) | In progress |
| Spec-driven development cycle | `features/README.md` | Complete |

## What needs to happen next

### Immediate (rebuild containers)
1. Rebuild `mcp` + `transcription-collector` → re-run MCP tests → should get 9+ PASS
2. Rebuild `bot-manager` + `dashboard` → run webhook tests with real meeting → validate envelope

### Next spec batches
3. MCP P1: expose chat/speak as MCP tools, add `search_meetings`
4. Webhooks P1: granular bot lifecycle events, multiple endpoints
5. Calendar: write RESEARCH.md from background agent, define feature scope
