"""Tests for webhook envelope building, HMAC signing, and header construction."""

import hashlib
import hmac
import time

import pytest
from shared_models.webhook_delivery import (
    WEBHOOK_API_VERSION,
    build_envelope,
    build_headers,
    clean_meeting_data,
    sign_payload,
)


# ---------------------------------------------------------------------------
# build_envelope
# ---------------------------------------------------------------------------

class TestBuildEnvelope:
    def test_has_exactly_5_keys(self):
        env = build_envelope("meeting.completed", {"id": 1})
        assert set(env.keys()) == {"event_id", "event_type", "api_version", "created_at", "data"}

    def test_event_id_prefix(self):
        env = build_envelope("meeting.completed", {"id": 1})
        assert env["event_id"].startswith("evt_")

    def test_event_id_unique(self):
        ids = {build_envelope("x", {})["event_id"] for _ in range(100)}
        assert len(ids) == 100

    def test_event_type_passthrough(self):
        env = build_envelope("meeting.status_changed", {"status": "active"})
        assert env["event_type"] == "meeting.status_changed"

    def test_data_passthrough(self):
        data = {"meeting_id": 42, "status": "completed"}
        env = build_envelope("x", data)
        assert env["data"] == data

    def test_custom_event_id(self):
        env = build_envelope("x", {}, event_id="evt_custom123")
        assert env["event_id"] == "evt_custom123"

    def test_created_at_is_iso(self):
        env = build_envelope("x", {})
        assert "T" in env["created_at"]  # ISO format


class TestWebhookApiVersion:
    def test_version_value(self):
        assert WEBHOOK_API_VERSION == "2026-03-01"


# ---------------------------------------------------------------------------
# clean_meeting_data
# ---------------------------------------------------------------------------

class TestCleanMeetingData:
    def test_strips_internal_keys(self):
        data = {
            "transcribe_enabled": True,
            "webhook_delivery": {"status": "delivered"},
            "webhook_deliveries": [1, 2],
            "webhook_secret": "secret123",
            "webhook_events": ["meeting.completed"],
            "custom_field": "keep",
        }
        clean = clean_meeting_data(data)
        assert "webhook_delivery" not in clean
        assert "webhook_deliveries" not in clean
        assert "webhook_secret" not in clean
        assert "webhook_events" not in clean
        assert clean["transcribe_enabled"] is True
        assert clean["custom_field"] == "keep"

    def test_none_returns_empty(self):
        assert clean_meeting_data(None) == {}

    def test_empty_returns_empty(self):
        assert clean_meeting_data({}) == {}

    def test_no_internal_keys_passes_through(self):
        data = {"foo": "bar", "baz": 42}
        assert clean_meeting_data(data) == data


# ---------------------------------------------------------------------------
# sign_payload
# ---------------------------------------------------------------------------

class TestSignPayload:
    def test_format(self):
        sig = sign_payload(b'{"test": true}', "secret")
        assert sig.startswith("sha256=")
        hex_part = sig[len("sha256="):]
        assert len(hex_part) == 64  # SHA-256 = 32 bytes = 64 hex chars

    def test_deterministic(self):
        payload = b'{"id": 1}'
        secret = "my-secret"
        sig1 = sign_payload(payload, secret)
        sig2 = sign_payload(payload, secret)
        assert sig1 == sig2

    def test_different_secret_different_sig(self):
        payload = b'{"id": 1}'
        sig1 = sign_payload(payload, "secret-a")
        sig2 = sign_payload(payload, "secret-b")
        assert sig1 != sig2

    def test_matches_manual_hmac(self):
        payload = b'hello world'
        secret = "test-secret"
        expected = "sha256=" + hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        assert sign_payload(payload, secret) == expected


# ---------------------------------------------------------------------------
# build_headers
# ---------------------------------------------------------------------------

class TestBuildHeaders:
    def test_no_secret_only_content_type(self):
        headers = build_headers()
        assert headers == {"Content-Type": "application/json"}

    def test_empty_secret_only_content_type(self):
        headers = build_headers(webhook_secret="  ")
        assert headers == {"Content-Type": "application/json"}

    def test_secret_without_payload_has_auth(self):
        headers = build_headers(webhook_secret="my-secret")
        assert headers["Authorization"] == "Bearer my-secret"
        assert "X-Webhook-Signature" not in headers

    def test_secret_with_payload_has_signature(self):
        headers = build_headers(
            webhook_secret="my-secret",
            payload_bytes=b'{"test": true}',
        )
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer my-secret"
        assert headers["X-Webhook-Signature"].startswith("sha256=")
        assert "X-Webhook-Timestamp" in headers

    def test_timestamp_is_recent(self):
        before = int(time.time())
        headers = build_headers(webhook_secret="s", payload_bytes=b"x")
        after = int(time.time())
        ts = int(headers["X-Webhook-Timestamp"])
        assert before <= ts <= after

    def test_signature_uses_timestamp_dot_payload(self):
        """Verify replay protection: signature covers timestamp.payload."""
        secret = "test"
        payload = b'{"data": 1}'
        headers = build_headers(webhook_secret=secret, payload_bytes=payload)
        ts = headers["X-Webhook-Timestamp"]
        # Reconstruct what should be signed
        signed_content = f"{ts}.".encode() + payload
        expected_sig = "sha256=" + hmac.new(
            secret.encode(), signed_content, hashlib.sha256
        ).hexdigest()
        assert headers["X-Webhook-Signature"] == expected_sig

    def test_whitespace_trimmed_from_secret(self):
        h1 = build_headers(webhook_secret="  secret  ")
        assert h1["Authorization"] == "Bearer secret"
