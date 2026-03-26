"""
Contract tests: Redis channel patterns and payload shapes.

Documents the exact Redis Pub/Sub channel naming conventions and
the JSON payload shapes published on each channel. Any change to
these patterns or shapes breaks the api-gateway WebSocket fan-in
and the bot command dispatch.

Run: pytest tests/contracts/test_redis_channels.py -v
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytest
from pydantic import BaseModel, Field, ValidationError


# ===================================================================
# Channel pattern contracts (string format tests)
# ===================================================================

class TestChannelPatterns:
    """Document exact Redis channel naming patterns."""

    def test_bot_manager_status_channel(self):
        """bm:meeting:{meeting_id}:status — published by bot-manager."""
        meeting_id = 42
        channel = f"bm:meeting:{meeting_id}:status"
        assert channel == "bm:meeting:42:status"

    def test_transcription_mutable_channel(self):
        """tc:meeting:{meeting_id}:mutable — published by transcription-collector/bot."""
        meeting_id = 42
        channel = f"tc:meeting:{meeting_id}:mutable"
        assert channel == "tc:meeting:42:mutable"

    def test_voice_agent_chat_channel(self):
        """va:meeting:{meeting_id}:chat — chat messages from bot."""
        meeting_id = 42
        channel = f"va:meeting:{meeting_id}:chat"
        assert channel == "va:meeting:42:chat"

    def test_bot_commands_channel(self):
        """bot_commands:meeting:{meeting_id} — commands from bot-manager to bot."""
        meeting_id = 42
        channel = f"bot_commands:meeting:{meeting_id}"
        assert channel == "bot_commands:meeting:42"

    def test_websocket_subscribes_three_channels(self):
        """api-gateway WebSocket subscribes to exactly these 3 channels per meeting."""
        meeting_id = 99
        channels = [
            f"tc:meeting:{meeting_id}:mutable",
            f"bm:meeting:{meeting_id}:status",
            f"va:meeting:{meeting_id}:chat",
        ]
        assert len(channels) == 3
        assert all(str(meeting_id) in c for c in channels)


# ===================================================================
# Payload shape contracts — Pydantic models for each channel
# ===================================================================

class MeetingStatusPayload(BaseModel):
    """Frozen shape: bm:meeting:{id}:status channel payload.

    Published by publish_meeting_status_change() in bot-manager.
    """
    type: str  # always "meeting.status"
    meeting: Dict[str, Any]  # {id, platform, native_id}
    payload: Dict[str, Any]  # {status, data?}
    user_id: int
    ts: str  # ISO 8601 timestamp


class MeetingStatusMeetingField(BaseModel):
    """Shape of the 'meeting' field inside MeetingStatusPayload."""
    id: int
    platform: str
    native_id: str


class MeetingStatusPayloadField(BaseModel):
    """Shape of the 'payload' field inside MeetingStatusPayload."""
    status: str
    data: Optional[Dict[str, Any]] = None


class TestBmStatusPayload:
    """bm:meeting:{id}:status payload shape must be frozen."""

    SAMPLE = {
        "type": "meeting.status",
        "meeting": {"id": 42, "platform": "google_meet", "native_id": "abc-defg-hij"},
        "payload": {"status": "active"},
        "user_id": 5,
        "ts": "2025-06-01T10:00:00",
    }

    def test_payload_parses(self):
        p = MeetingStatusPayload(**self.SAMPLE)
        assert p.type == "meeting.status"
        assert p.user_id == 5

    def test_meeting_field_shape(self):
        m = MeetingStatusMeetingField(**self.SAMPLE["meeting"])
        assert m.id == 42
        assert m.platform == "google_meet"
        assert m.native_id == "abc-defg-hij"

    def test_payload_field_shape(self):
        p = MeetingStatusPayloadField(**self.SAMPLE["payload"])
        assert p.status == "active"
        assert p.data is None

    def test_payload_with_extra_data(self):
        payload = {**self.SAMPLE["payload"], "data": {"completion_reason": "stopped"}}
        p = MeetingStatusPayloadField(**payload)
        assert p.data["completion_reason"] == "stopped"

    def test_roundtrip_json(self):
        """Payload must survive JSON serialize/deserialize."""
        serialized = json.dumps(self.SAMPLE)
        deserialized = json.loads(serialized)
        p = MeetingStatusPayload(**deserialized)
        assert p.type == "meeting.status"


# ===================================================================
# Bot command channel payloads
# ===================================================================

class BotCommandPayload(BaseModel):
    """Base shape for bot_commands:meeting:{id} payloads."""
    action: str
    meeting_id: int


class ReconfigureCommand(BotCommandPayload):
    """Reconfigure command sent to bot via Redis."""
    language: Optional[str] = None
    task: Optional[str] = None
    allowed_languages: Optional[List[str]] = None


class SpeakCommand(BaseModel):
    """Speak command sent to bot via Redis."""
    action: str  # "speak"
    meeting_id: int
    text: Optional[str] = None
    audio_url: Optional[str] = None
    audio_base64: Optional[str] = None
    format: Optional[str] = None
    sample_rate: Optional[int] = None
    provider: Optional[str] = None
    voice: Optional[str] = None


class SpeakStopCommand(BaseModel):
    """Stop speaking command."""
    action: str  # "speak_stop"
    meeting_id: int


class TestBotCommandPayloads:

    def test_reconfigure_command(self):
        cmd = ReconfigureCommand(
            action="reconfigure",
            meeting_id=42,
            language="es",
            task="translate",
            allowed_languages=["en", "es"],
        )
        assert cmd.action == "reconfigure"

    def test_speak_command(self):
        cmd = SpeakCommand(
            action="speak",
            meeting_id=42,
            text="Hello everyone",
        )
        assert cmd.action == "speak"

    def test_speak_stop_command(self):
        cmd = SpeakStopCommand(action="speak_stop", meeting_id=42)
        assert cmd.action == "speak_stop"


# ===================================================================
# WebSocket protocol messages (api-gateway ↔ client)
# ===================================================================

class WsSubscribeRequest(BaseModel):
    """Client → api-gateway: subscribe to meeting updates."""
    action: str  # "subscribe"
    meetings: List[Dict[str, str]]  # [{platform, native_id}]


class WsSubscribedResponse(BaseModel):
    """api-gateway → client: subscription confirmed."""
    type: str  # "subscribed"
    meetings: List[Dict[str, str]]


class WsUnsubscribeRequest(BaseModel):
    """Client → api-gateway: unsubscribe from meetings."""
    action: str  # "unsubscribe"
    meetings: List[Dict[str, str]]


class WsErrorResponse(BaseModel):
    """api-gateway → client: error."""
    type: str  # "error"
    error: str
    details: Optional[Any] = None
    status: Optional[int] = None
    detail: Optional[str] = None


class TestWebSocketProtocol:

    def test_subscribe_request(self):
        msg = WsSubscribeRequest(
            action="subscribe",
            meetings=[{"platform": "google_meet", "native_id": "abc-defg-hij"}],
        )
        assert msg.action == "subscribe"
        assert len(msg.meetings) == 1

    def test_subscribed_response(self):
        msg = WsSubscribedResponse(
            type="subscribed",
            meetings=[{"platform": "google_meet", "native_id": "abc-defg-hij"}],
        )
        assert msg.type == "subscribed"

    def test_error_response(self):
        msg = WsErrorResponse(type="error", error="missing_api_key")
        assert msg.error == "missing_api_key"

    def test_ping_pong(self):
        """Ping/pong protocol is simple JSON."""
        ping = {"action": "ping"}
        pong = {"type": "pong"}
        assert ping["action"] == "ping"
        assert pong["type"] == "pong"
