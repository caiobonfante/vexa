"""Webhook delivery — thin wrapper over shared_models.webhook_delivery.

Preserves the exact HMAC signing algorithm, envelope format, and header
contracts from bot-manager. See tests/contracts/test_webhook_contracts.py.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from shared_models.models import Meeting, User
from shared_models.webhook_url import validate_webhook_url
from shared_models.webhook_delivery import (
    deliver,
    build_envelope,
    clean_meeting_data,
    get_redis_client,
)

logger = logging.getLogger("meeting_api.webhooks")

# Map meeting status to webhook event type
STATUS_TO_EVENT: Dict[str, str] = {
    "completed": "meeting.completed",
    "active": "meeting.started",
    "failed": "bot.failed",
}


def _resolve_event_type(meeting_status: str) -> str:
    return STATUS_TO_EVENT.get(meeting_status, "meeting.status_change")


def _is_event_enabled(user_data: Optional[Dict], event_type: str) -> bool:
    default_enabled = {"meeting.completed"}
    events_config = (user_data or {}).get("webhook_events")
    if not events_config or not isinstance(events_config, dict):
        return event_type in default_enabled
    enabled = events_config.get(event_type)
    if enabled is not None:
        return bool(enabled)
    return event_type in default_enabled


def _write_delivery_status(meeting: Meeting, status: dict):
    data = dict(meeting.data) if meeting.data else {}
    data["webhook_delivery"] = status
    meeting.data = data
    flag_modified(meeting, "data")


def _build_meeting_event_data(meeting: Meeting) -> Dict[str, Any]:
    """Build the meeting data dict used in webhook payloads."""
    return {
        "id": meeting.id,
        "user_id": meeting.user_id,
        "platform": meeting.platform,
        "native_meeting_id": meeting.native_meeting_id,
        "constructed_meeting_url": meeting.constructed_meeting_url,
        "status": meeting.status,
        "start_time": meeting.start_time.isoformat() if meeting.start_time else None,
        "end_time": meeting.end_time.isoformat() if meeting.end_time else None,
        "data": clean_meeting_data(meeting.data),
        "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
        "updated_at": meeting.updated_at.isoformat() if meeting.updated_at else None,
    }


async def send_completion_webhook(meeting: Meeting, db: AsyncSession):
    """Post-meeting webhook — called from post_meeting tasks (same as bot_exit_tasks/send_webhook.py)."""
    try:
        user = meeting.user
        if not user:
            return

        webhook_url = user.data.get("webhook_url") if user.data and isinstance(user.data, dict) else None
        if not webhook_url:
            return

        try:
            validate_webhook_url(webhook_url)
        except ValueError:
            return

        webhook_secret = user.data.get("webhook_secret") if isinstance(user.data, dict) else None

        payload = build_envelope("meeting.completed", {"meeting": _build_meeting_event_data(meeting)})
        now = datetime.now(timezone.utc).isoformat()

        resp = await deliver(
            url=webhook_url,
            payload=payload,
            webhook_secret=webhook_secret,
            timeout=30.0,
            label=f"client-webhook meeting={meeting.id} user={user.email}",
            metadata={"meeting_id": meeting.id},
        )

        if resp is not None:
            _write_delivery_status(meeting, {
                "url": webhook_url,
                "status_code": resp.status_code,
                "attempts": 1,
                "delivered_at": now,
                "status": "delivered",
            })
        else:
            effective_redis = get_redis_client()
            if effective_redis is not None:
                _write_delivery_status(meeting, {
                    "url": webhook_url,
                    "attempts": 0,
                    "status": "queued",
                    "queued_at": now,
                })
            else:
                _write_delivery_status(meeting, {
                    "url": webhook_url,
                    "attempts": 3,
                    "status": "failed",
                    "failed_at": now,
                })
    except Exception as e:
        logger.error(f"Unexpected error sending webhook for meeting {meeting.id}: {e}", exc_info=True)


async def send_status_webhook(
    meeting: Meeting,
    db: AsyncSession,
    status_change_info: Optional[Dict[str, Any]] = None,
):
    """Status-change webhook — called on every transition (same as tasks/send_status_webhook.py)."""
    try:
        user = meeting.user
        if not user:
            return

        webhook_url = user.data.get("webhook_url") if user.data and isinstance(user.data, dict) else None
        if not webhook_url:
            return

        event_type = _resolve_event_type(meeting.status)
        if not _is_event_enabled(user.data, event_type):
            return

        try:
            validate_webhook_url(webhook_url)
        except ValueError:
            return

        webhook_secret = user.data.get("webhook_secret") if isinstance(user.data, dict) else None

        event_data: Dict[str, Any] = {"meeting": _build_meeting_event_data(meeting)}

        if status_change_info:
            event_data["status_change"] = {
                "from": status_change_info.get("old_status"),
                "to": status_change_info.get("new_status", meeting.status),
                "reason": status_change_info.get("reason"),
                "timestamp": status_change_info.get("timestamp"),
                "transition_source": status_change_info.get("transition_source"),
            }

        payload = build_envelope(event_type, event_data)
        await deliver(
            url=webhook_url,
            payload=payload,
            webhook_secret=webhook_secret,
            timeout=30.0,
            label=f"status-webhook meeting={meeting.id} status={meeting.status}",
        )
    except Exception as e:
        logger.error(f"Unexpected error sending status webhook for meeting {meeting.id}: {e}", exc_info=True)


async def send_event_webhook(user_id: int, event_type: str, data: dict):
    """Fire-and-forget webhook for recording/transcription events."""
    from shared_models.database import async_session_local

    try:
        async with async_session_local() as db:
            user = await db.get(User, user_id)
            if not user or not user.data or not isinstance(user.data, dict):
                return
            webhook_url = user.data.get("webhook_url")
            if not webhook_url:
                return
            try:
                validate_webhook_url(webhook_url)
            except ValueError:
                return
            webhook_secret = user.data.get("webhook_secret")

        payload = build_envelope(event_type, data)
        await deliver(
            url=webhook_url,
            payload=payload,
            webhook_secret=webhook_secret,
            timeout=30.0,
            label=f"event-webhook {event_type} user={user_id}",
        )
    except Exception as e:
        logger.warning(f"Event webhook ({event_type}) failed for user {user_id}: {e}")
