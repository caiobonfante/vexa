# Webhooks Test Findings

## Gate verdict: PASS (code validated in running container)

## Test run: 2026-03-23 (post-rebuild)

P0 envelope standardization validated by running code in the rebuilt bot-manager container. End-to-end delivery blocked by SSRF protection (private IPs blocked by design — correct behavior for production).

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Webhook URL configurable | 80 | PUT /user/webhook = 200 with public URL | 2026-03-23 (live) | — |
| SSRF protection | 90 | Private IPs correctly blocked | 2026-03-23 (live) | — |
| Status webhook scheduled | 90 | Bot-manager log: "Scheduled status webhook task for meeting 651" | 2026-03-23 (live log) | — |
| Webhook task runner fires | 90 | Bot-manager log: "Starting webhook task runner for meeting 651" | 2026-03-23 (live log) | — |
| build_envelope in container | 90 | `docker exec` test: event_id=evt_..., event_type, api_version, created_at, data all present | 2026-03-23 (container exec) | — |
| clean_meeting_data works | 90 | `docker exec` test: webhook_delivery, webhook_secret stripped; bot_config kept | 2026-03-23 (container exec) | — |
| bot_container_id removed | 90 | `inspect.getsource()` confirms not in send_status_webhook.run() | 2026-03-23 (container exec) | — |
| send_status_webhook uses envelope | 90 | `inspect.getsource()` confirms build_envelope + clean_meeting_data used | 2026-03-23 (container exec) | — |
| End-to-end delivery | 60 | Code runs but SSRF blocks private receiver URL (correct behavior) | 2026-03-23 (live log) | Test with public webhook URL |
| Durable retry | 80 | Retry worker started in bot-manager logs | 2026-03-23 (live log) | Verify Redis queue on failure |

## Validated P0 changes (in running container)

### Envelope format (verified via `docker exec`)
```python
{
    "event_id": "evt_e0d4cad81c514ee0a3fe023aa6321a61",
    "event_type": "meeting.started",
    "api_version": "2026-03-01",
    "created_at": "2026-03-22T23:52:28.343956+00:00",
    "data": {"meeting": {"id": 123, "status": "joining"}}
}
```

### Internal data filtering (verified via `docker exec`)
- `webhook_delivery` → stripped
- `webhook_secret` → stripped
- `webhook_events` → stripped
- `webhook_deliveries` → stripped
- `bot_container_id` → removed from payload

### Code path verification (verified via `inspect.getsource()`)
- `send_status_webhook.py` uses `build_envelope()` → True
- `send_status_webhook.py` uses `clean_meeting_data()` → True
- `send_status_webhook.py` contains `bot_container_id` → False

## How to reproduce

```bash
# Container verification
docker exec vexa-restore-bot-manager-1 python3 -c "
from shared_models.webhook_delivery import build_envelope, clean_meeting_data
payload = build_envelope('test', {'meeting': {'id': 1}})
print(list(payload.keys()))  # ['event_id', 'event_type', 'api_version', 'created_at', 'data']
"

# End-to-end (requires public webhook URL)
cd features/webhooks/tests
# Set WEBHOOK_URL to a public endpoint (e.g., webhook.site)
make test
```

## Next steps
- Test with public webhook URL for full end-to-end validation
- P1 spec: granular bot lifecycle events, multiple endpoints
