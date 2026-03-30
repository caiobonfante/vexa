# Webhooks P0 Spec: Envelope Standardization

## Items

### 1. Standardize payload envelope

**Current behavior:** Three different payload formats:

| Source | Field | Shape |
|--------|-------|-------|
| `send_status_webhook.py` | `event_type` | `{event_type, meeting, status_change}` |
| `send_webhook.py` | (none) | Flat meeting fields at top level |
| `post_meeting_hooks.py` | `event` | `{event, meeting}` |

**Expected behavior:** ALL webhook payloads use this envelope:

```json
{
  "event_id": "evt_<uuid4_hex>",
  "event_type": "meeting.completed",
  "api_version": "2026-03-01",
  "created_at": "2026-03-23T20:10:12+00:00",
  "data": {
    "meeting": { ... },
    "status_change": { ... }
  }
}
```

Rules:
- `event_id` — unique UUID for idempotency, prefixed with `evt_`
- `event_type` — always present, always this field name (not `event`)
- `api_version` — constant string, bumped on breaking changes
- `created_at` — always timezone-aware ISO 8601 (UTC)
- `data` — event-specific payload, always an object

**Test assertions:**
1. Received webhook has `event_id` field starting with `evt_`
2. Received webhook has `event_type` field (not `event`, not missing)
3. Received webhook has `api_version` field
4. Received webhook has `created_at` field with timezone info
5. Received webhook has `data` object field
6. No meeting fields at top level (id, user_id, platform should be inside `data.meeting`)

### 2. Remove internal data from payloads

**Current behavior:**
- `bot_container_id` (Docker container ID) exposed in meeting object
- `meeting.data` raw JSONB included — leaks `webhook_delivery` status, internal config

**Expected behavior:**
- No `bot_container_id` in webhook payloads
- `meeting.data` filtered to exclude: `webhook_delivery`, `webhook_deliveries`, `webhook_secret`, `webhook_events`

**Test assertions:**
1. Received webhook does not contain `bot_container_id`
2. Received webhook `data.meeting` does not contain `webhook_delivery` key
3. Received webhook `data.meeting` does not contain `webhook_secret` key

### 3. Fix test webhook signing

**Current behavior:** Dashboard test endpoint signs `hmac(payload)`. Production signs `hmac(timestamp.payload)`.

**Expected behavior:** Test webhook uses same signing as production:
- `X-Webhook-Signature: sha256=<hmac of timestamp.payload>`
- `X-Webhook-Timestamp: <unix timestamp>`
- Signing input: `"{timestamp}.{payload_bytes}"`

**Test assertions:**
1. Test webhook includes `X-Webhook-Signature` header
2. Test webhook includes `X-Webhook-Timestamp` header
3. Signature is verifiable using `hmac(timestamp + "." + payload, secret)`

### 4. Add event_id to webhook_delivery.py

**Current behavior:** `deliver()` accepts a payload dict with no event_id.

**Expected behavior:** Callers pass event_id, or `deliver()` generates one if missing.
- `build_envelope()` helper creates the standard envelope
- All callers use `build_envelope()` instead of constructing payloads manually

## Implementation notes

### Envelope helper (new function in webhook_delivery.py)

```python
def build_envelope(event_type: str, data: dict, event_id: str = None) -> dict:
    """Build a standardized webhook envelope."""
    return {
        "event_id": event_id or f"evt_{uuid4().hex}",
        "event_type": event_type,
        "api_version": "2026-03-01",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
```

### Files to modify

1. `libs/shared-models/shared_models/webhook_delivery.py` — add `build_envelope()`
2. `packages/meeting-api/meeting_api/webhooks.py` — use `build_envelope()`, remove `bot_container_id`, filter `meeting.data`
3. `packages/meeting-api/meeting_api/webhook_delivery.py` — use `build_envelope()`, wrap in `data.meeting`
4. `packages/meeting-api/meeting_api/post_meeting.py` — use `build_envelope()`, change `event` to `event_type`
5. `services/dashboard/src/app/api/webhooks/test/route.ts` — fix signing to use `timestamp.payload`

### Meeting data filtering

```python
INTERNAL_KEYS = {"webhook_delivery", "webhook_deliveries", "webhook_secret", "webhook_events"}

def clean_meeting_data(data: dict) -> dict:
    """Remove internal keys from meeting.data before webhook delivery."""
    return {k: v for k, v in (data or {}).items() if k not in INTERNAL_KEYS}
```
