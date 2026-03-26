"""
Contract tests: Webhook delivery format.

Documents the HMAC signature format, webhook envelope shape,
and header contracts. Any change here breaks customer webhook
integrations.

Run: pytest tests/contracts/test_webhook_contracts.py -v
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional
from uuid import uuid4

import pytest
from pydantic import BaseModel, Field

from shared_models.webhook_delivery import (
    WEBHOOK_API_VERSION,
    build_envelope,
    build_headers,
    sign_payload,
    clean_meeting_data,
)


# ===================================================================
# 1. Webhook envelope shape
# ===================================================================

class WebhookEnvelope(BaseModel):
    """Frozen shape of all webhook payloads."""
    event_id: str
    event_type: str
    api_version: str
    created_at: str  # ISO 8601
    data: Dict[str, Any]


class TestWebhookEnvelope:

    def test_build_envelope_shape(self):
        """build_envelope() must produce exactly these 5 keys."""
        envelope = build_envelope("meeting.completed", {"meeting_id": 42})
        parsed = WebhookEnvelope(**envelope)
        assert parsed.event_type == "meeting.completed"
        assert parsed.api_version == WEBHOOK_API_VERSION
        assert parsed.data == {"meeting_id": 42}
        assert parsed.event_id.startswith("evt_")

    def test_envelope_field_names(self):
        expected = {"event_id", "event_type", "api_version", "created_at", "data"}
        assert set(WebhookEnvelope.model_fields.keys()) == expected

    def test_custom_event_id(self):
        envelope = build_envelope("test.event", {}, event_id="evt_custom123")
        assert envelope["event_id"] == "evt_custom123"

    def test_api_version_frozen(self):
        """API version must not silently change."""
        assert WEBHOOK_API_VERSION == "2026-03-01"

    def test_envelope_created_at_is_iso(self):
        envelope = build_envelope("test", {})
        # Must be parseable as ISO 8601
        from datetime import datetime
        dt = datetime.fromisoformat(envelope["created_at"].replace("Z", "+00:00"))
        assert dt.year >= 2025


# ===================================================================
# 2. HMAC signature format
# ===================================================================

class TestHmacSignature:

    def test_sign_payload_format(self):
        """Signature must be 'sha256=<hex>'."""
        payload = b'{"test": true}'
        sig = sign_payload(payload, "my-secret")
        assert sig.startswith("sha256=")
        hex_part = sig.split("=", 1)[1]
        assert len(hex_part) == 64  # SHA-256 hex is 64 chars

    def test_sign_payload_deterministic(self):
        payload = b'{"test": true}'
        sig1 = sign_payload(payload, "secret")
        sig2 = sign_payload(payload, "secret")
        assert sig1 == sig2

    def test_sign_payload_different_secrets(self):
        payload = b'{"test": true}'
        sig1 = sign_payload(payload, "secret-a")
        sig2 = sign_payload(payload, "secret-b")
        assert sig1 != sig2

    def test_sign_payload_matches_manual_hmac(self):
        """Verify against a manual HMAC computation."""
        payload = b'hello world'
        secret = "test-secret"
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        sig = sign_payload(payload, secret)
        assert sig == f"sha256={expected}"


# ===================================================================
# 3. Webhook headers contract
# ===================================================================

class TestWebhookHeaders:

    def test_headers_without_secret(self):
        """Without secret, only Content-Type is set."""
        headers = build_headers()
        assert headers == {"Content-Type": "application/json"}

    def test_headers_with_secret_no_payload(self):
        """With secret but no payload: Bearer token only."""
        headers = build_headers(webhook_secret="my-secret")
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer my-secret"
        assert "X-Webhook-Signature" not in headers

    def test_headers_with_secret_and_payload(self):
        """Full headers: Bearer + X-Webhook-Signature + X-Webhook-Timestamp."""
        payload_bytes = b'{"event": "test"}'
        headers = build_headers(webhook_secret="my-secret", payload_bytes=payload_bytes)
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer my-secret"
        assert "X-Webhook-Signature" in headers
        assert "X-Webhook-Timestamp" in headers
        assert headers["X-Webhook-Signature"].startswith("sha256=")

    def test_signature_includes_timestamp(self):
        """Signature is computed over '{timestamp}.{payload}' for replay protection."""
        payload_bytes = b'{"event": "test"}'
        secret = "my-secret"
        headers = build_headers(webhook_secret=secret, payload_bytes=payload_bytes)
        ts = headers["X-Webhook-Timestamp"]
        sig_hex = headers["X-Webhook-Signature"].split("=", 1)[1]

        # Recompute
        signed_content = f"{ts}.".encode() + payload_bytes
        expected = hmac.new(secret.encode(), signed_content, hashlib.sha256).hexdigest()
        assert sig_hex == expected

    def test_header_keys_frozen(self):
        """Document the exact header key names."""
        payload_bytes = b'{}'
        headers = build_headers(webhook_secret="s", payload_bytes=payload_bytes)
        expected_keys = {
            "Content-Type",
            "Authorization",
            "X-Webhook-Signature",
            "X-Webhook-Timestamp",
        }
        assert set(headers.keys()) == expected_keys

    def test_whitespace_secret_stripped(self):
        h1 = build_headers(webhook_secret="  secret  ")
        assert h1["Authorization"] == "Bearer secret"

    def test_empty_secret_no_auth(self):
        headers = build_headers(webhook_secret="   ")
        assert "Authorization" not in headers


# ===================================================================
# 4. Internal data stripping
# ===================================================================

class TestCleanMeetingData:

    def test_strips_internal_keys(self):
        data = {
            "name": "My Meeting",
            "webhook_delivery": {"some": "data"},
            "webhook_deliveries": [1, 2],
            "webhook_secret": "shh",
            "webhook_events": ["e1"],
            "participants": ["Alice"],
        }
        cleaned = clean_meeting_data(data)
        assert "name" in cleaned
        assert "participants" in cleaned
        assert "webhook_delivery" not in cleaned
        assert "webhook_deliveries" not in cleaned
        assert "webhook_secret" not in cleaned
        assert "webhook_events" not in cleaned

    def test_none_data(self):
        assert clean_meeting_data(None) == {}

    def test_empty_data(self):
        assert clean_meeting_data({}) == {}

    def test_no_internal_keys(self):
        data = {"name": "Test", "notes": "some notes"}
        assert clean_meeting_data(data) == data
