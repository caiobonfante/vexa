"""Tests for webhook delivery logic."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared_models.models import Meeting, User

from .conftest import make_meeting, make_user, TEST_MEETING_ID, TEST_USER_ID


# ===================================================================
# Webhook helper functions
# ===================================================================


class TestWebhookHelpers:

    def test_resolve_event_type(self):
        """Status → event type mapping."""
        from meeting_api.webhooks import _resolve_event_type

        assert _resolve_event_type("completed") == "meeting.completed"
        assert _resolve_event_type("active") == "meeting.started"
        assert _resolve_event_type("failed") == "bot.failed"
        assert _resolve_event_type("joining") == "meeting.status_change"

    def test_is_event_enabled_defaults(self):
        """Default: only meeting.completed is enabled."""
        from meeting_api.webhooks import _is_event_enabled

        assert _is_event_enabled(None, "meeting.completed") is True
        assert _is_event_enabled(None, "meeting.started") is False
        assert _is_event_enabled({}, "meeting.completed") is True

    def test_is_event_enabled_custom_config(self):
        """User can enable/disable events via webhook_events config."""
        from meeting_api.webhooks import _is_event_enabled

        user_data = {
            "webhook_events": {
                "meeting.completed": True,
                "meeting.started": True,
                "bot.failed": False,
            }
        }
        assert _is_event_enabled(user_data, "meeting.completed") is True
        assert _is_event_enabled(user_data, "meeting.started") is True
        assert _is_event_enabled(user_data, "bot.failed") is False

    def test_build_meeting_event_data(self):
        """Event data includes frozen meeting fields."""
        from meeting_api.webhooks import _build_meeting_event_data

        now = datetime.utcnow()
        meeting = make_meeting(
            status="completed",
            start_time=now,
            end_time=now,
            constructed_meeting_url="https://meet.google.com/abc",
        )
        # Add native_meeting_id property
        object.__setattr__(meeting, "native_meeting_id", "abc-defg-hij")

        data = _build_meeting_event_data(meeting)
        assert data["id"] == TEST_MEETING_ID
        assert data["user_id"] == TEST_USER_ID
        assert data["platform"] == "google_meet"
        assert data["status"] == "completed"


# ===================================================================
# send_completion_webhook
# ===================================================================


class TestSendCompletionWebhook:

    @pytest.mark.asyncio
    async def test_no_user_skips(self):
        """No user on meeting → skip webhook."""
        from meeting_api.webhooks import send_completion_webhook

        meeting = make_meeting()
        object.__setattr__(meeting, "user", None)

        db = AsyncMock()
        await send_completion_webhook(meeting, db)
        # Should not raise, just return

    @pytest.mark.asyncio
    async def test_no_webhook_url_skips(self):
        """User with no webhook_url → skip webhook."""
        from meeting_api.webhooks import send_completion_webhook

        user = make_user(data={})
        meeting = make_meeting()
        object.__setattr__(meeting, "user", user)

        db = AsyncMock()
        await send_completion_webhook(meeting, db)

    @pytest.mark.asyncio
    async def test_webhook_calls_deliver(self):
        """Webhook with valid URL → calls deliver()."""
        from meeting_api.webhooks import send_completion_webhook

        user = make_user(data={"webhook_url": "https://example.com/webhook"})
        now = datetime.utcnow()
        meeting = make_meeting(
            status="completed",
            start_time=now,
            end_time=now,
        )
        object.__setattr__(meeting, "user", user)
        object.__setattr__(meeting, "native_meeting_id", "abc-defg-hij")
        object.__setattr__(meeting, "constructed_meeting_url", "https://meet.google.com/abc")

        db = AsyncMock()

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("meeting_api.webhooks.deliver", new_callable=AsyncMock, return_value=mock_resp):
            with patch("meeting_api.webhooks.validate_webhook_url"):
                with patch("meeting_api.webhooks.build_envelope", return_value={"event": "test"}):
                    await send_completion_webhook(meeting, db)


# ===================================================================
# Webhook HMAC signing
# ===================================================================


class TestWebhookSigning:

    @pytest.mark.asyncio
    async def test_webhook_with_secret_uses_hmac(self):
        """When user has webhook_secret, deliver is called with it."""
        from meeting_api.webhooks import send_completion_webhook

        user = make_user(data={
            "webhook_url": "https://example.com/webhook",
            "webhook_secret": "my-secret-key",
        })
        now = datetime.utcnow()
        meeting = make_meeting(status="completed", start_time=now, end_time=now)
        object.__setattr__(meeting, "user", user)
        object.__setattr__(meeting, "native_meeting_id", "abc-defg-hij")
        object.__setattr__(meeting, "constructed_meeting_url", None)

        db = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("meeting_api.webhooks.deliver", new_callable=AsyncMock, return_value=mock_resp) as mock_deliver:
            with patch("meeting_api.webhooks.validate_webhook_url"):
                with patch("meeting_api.webhooks.build_envelope", return_value={"event": "test"}):
                    await send_completion_webhook(meeting, db)

        mock_deliver.assert_called_once()
        call_kwargs = mock_deliver.call_args[1]
        assert call_kwargs["webhook_secret"] == "my-secret-key"

    @pytest.mark.asyncio
    async def test_webhook_without_secret_no_signature(self):
        """When no webhook_secret, deliver is called with None secret."""
        from meeting_api.webhooks import send_completion_webhook

        user = make_user(data={
            "webhook_url": "https://example.com/webhook",
        })
        now = datetime.utcnow()
        meeting = make_meeting(status="completed", start_time=now, end_time=now)
        object.__setattr__(meeting, "user", user)
        object.__setattr__(meeting, "native_meeting_id", "abc-defg-hij")
        object.__setattr__(meeting, "constructed_meeting_url", None)

        db = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("meeting_api.webhooks.deliver", new_callable=AsyncMock, return_value=mock_resp) as mock_deliver:
            with patch("meeting_api.webhooks.validate_webhook_url"):
                with patch("meeting_api.webhooks.build_envelope", return_value={"event": "test"}):
                    await send_completion_webhook(meeting, db)

        call_kwargs = mock_deliver.call_args[1]
        assert call_kwargs["webhook_secret"] is None
