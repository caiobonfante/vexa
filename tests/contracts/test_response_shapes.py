"""
Contract tests: API response shapes.

These Pydantic models capture the EXACT response shapes of frozen endpoints.
Any refactoring that changes these shapes breaks downstream consumers
(dashboard, MCP server, webhooks).

Run: pytest tests/contracts/test_response_shapes.py -v
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytest
from pydantic import BaseModel, ValidationError

# ---------------------------------------------------------------------------
# Import the live schemas — if these imports fail, the contract is broken.
# ---------------------------------------------------------------------------
from shared_models.schemas import (
    BotStatus,
    BotStatusResponse,
    MeetingCreate,
    MeetingResponse,
    MeetingStatus,
    MeetingCompletionReason,
    MeetingFailureStage,
    Platform,
    RecordingResponse,
    RecordingListResponse,
    RecordingStatus,
    RecordingSource,
    MediaFileResponse,
    MediaFileType,
    ChatMessage,
    ChatMessagesResponse,
    SpeakRequest,
)


# ===================================================================
# 1. GET /bots/status  →  BotStatusResponse
# ===================================================================

class TestBotStatusContract:
    """The BotStatus / BotStatusResponse shape must remain stable."""

    MINIMAL_BOT = {
        "container_id": "abc123",
        "container_name": "vexa-bot-42",
        "platform": "google_meet",
        "native_meeting_id": "abc-defg-hij",
        "status": "running",
        "normalized_status": "Up",
        "created_at": "2025-01-01T00:00:00",
        "start_time": "2025-01-01T00:01:00",
        "labels": {"user_id": "5"},
        "meeting_id_from_name": "42",
        "data": {"some": "metadata"},
    }

    def test_full_bot_status(self):
        """All documented fields must be accepted."""
        bot = BotStatus(**self.MINIMAL_BOT)
        assert bot.container_id == "abc123"
        assert bot.container_name == "vexa-bot-42"
        assert bot.platform == "google_meet"
        assert bot.native_meeting_id == "abc-defg-hij"
        assert bot.status == "running"
        assert bot.normalized_status == "Up"
        assert bot.meeting_id_from_name == "42"
        assert bot.data == {"some": "metadata"}

    def test_all_fields_optional(self):
        """BotStatus must accept an entirely empty dict (all Optional)."""
        bot = BotStatus()
        assert bot.container_id is None
        assert bot.platform is None

    def test_response_wraps_list(self):
        """BotStatusResponse.running_bots must be a list of BotStatus."""
        resp = BotStatusResponse(running_bots=[
            BotStatus(**self.MINIMAL_BOT),
            BotStatus(),
        ])
        assert len(resp.running_bots) == 2

    def test_empty_running_bots(self):
        resp = BotStatusResponse(running_bots=[])
        assert resp.running_bots == []

    @pytest.mark.parametrize("ns", [
        "Requested", "Starting", "Up", "Stopping", "Exited", "Failed",
    ])
    def test_normalized_status_allowed_values(self, ns):
        """Only these six normalized_status values are valid."""
        bot = BotStatus(normalized_status=ns)
        assert bot.normalized_status == ns

    def test_normalized_status_rejects_unknown(self):
        with pytest.raises(ValidationError):
            BotStatus(normalized_status="bogus")

    def test_bot_status_required_fields_contract(self):
        """Document that BotStatus has exactly these field names."""
        expected_fields = {
            "container_id", "container_name", "platform",
            "native_meeting_id", "status", "normalized_status",
            "created_at", "start_time", "labels",
            "meeting_id_from_name", "data",
        }
        assert set(BotStatus.model_fields.keys()) == expected_fields


# ===================================================================
# 2. POST /bots  →  MeetingResponse
# ===================================================================

class TestMeetingResponseContract:
    """POST /bots returns MeetingResponse — shape must be frozen."""

    SAMPLE = {
        "id": 1,
        "user_id": 5,
        "platform": "google_meet",
        "native_meeting_id": "abc-defg-hij",
        "constructed_meeting_url": "https://meet.google.com/abc-defg-hij",
        "status": "requested",
        "bot_container_id": "container-xyz",
        "start_time": "2025-06-01T10:00:00",
        "end_time": None,
        "data": {"name": "Test Meeting"},
        "created_at": "2025-06-01T09:59:00",
        "updated_at": "2025-06-01T10:00:00",
    }

    def test_full_meeting_response(self):
        resp = MeetingResponse(**self.SAMPLE)
        assert resp.id == 1
        assert resp.user_id == 5
        assert resp.platform == "google_meet"
        assert resp.status == MeetingStatus.REQUESTED

    def test_meeting_response_field_names(self):
        """Document the frozen field set."""
        expected = {
            "id", "user_id", "platform", "native_meeting_id",
            "constructed_meeting_url", "status", "bot_container_id",
            "start_time", "end_time", "data", "created_at", "updated_at",
        }
        assert set(MeetingResponse.model_fields.keys()) == expected

    def test_status_enum_values(self):
        """All MeetingStatus values are frozen."""
        expected = {
            "requested", "joining", "awaiting_admission", "active",
            "needs_human_help", "stopping", "completed", "failed",
        }
        assert {s.value for s in MeetingStatus} == expected

    def test_completion_reason_values(self):
        expected = {
            "stopped", "validation_error", "awaiting_admission_timeout",
            "awaiting_admission_rejected", "left_alone", "evicted",
        }
        assert {r.value for r in MeetingCompletionReason} == expected

    def test_failure_stage_values(self):
        expected = {"requested", "joining", "awaiting_admission", "active"}
        assert {s.value for s in MeetingFailureStage} == expected

    def test_platform_enum_values(self):
        expected = {"google_meet", "zoom", "teams", "browser_session"}
        assert {p.value for p in Platform} == expected


# ===================================================================
# 3. MeetingCreate (POST /bots request body)
# ===================================================================

class TestMeetingCreateContract:
    """POST /bots request body shape must be frozen."""

    def test_minimal_google_meet(self):
        req = MeetingCreate(
            platform="google_meet",
            native_meeting_id="abc-defg-hij",
        )
        assert req.platform == Platform.GOOGLE_MEET

    def test_minimal_teams(self):
        req = MeetingCreate(
            platform="teams",
            native_meeting_id="1234567890",
            passcode="ABC123",
        )
        assert req.platform == Platform.TEAMS

    def test_agent_only(self):
        req = MeetingCreate(agent_enabled=True)
        assert req.agent_enabled is True
        assert req.platform is None

    def test_browser_session_mode(self):
        req = MeetingCreate(mode="browser_session")
        assert req.mode == "browser_session"

    def test_all_optional_fields_accepted(self):
        """Verify every optional field is present and typed correctly."""
        req = MeetingCreate(
            platform="google_meet",
            native_meeting_id="abc-defg-hij",
            bot_name="MyBot",
            language="en",
            task="transcribe",
            transcription_tier="realtime",
            recording_enabled=True,
            transcribe_enabled=True,
            voice_agent_enabled=True,
            default_avatar_url="https://example.com/avatar.png",
            agent_enabled=False,
            video=True,
            authenticated=False,
        )
        assert req.bot_name == "MyBot"

    def test_meeting_create_field_names(self):
        expected = {
            "platform", "native_meeting_id", "bot_name", "language",
            "task", "transcription_tier", "recording_enabled",
            "transcribe_enabled", "passcode", "meeting_url",
            "teams_base_host", "zoom_obf_token", "voice_agent_enabled",
            "default_avatar_url", "agent_enabled", "mode", "video",
            "authenticated",
        }
        assert set(MeetingCreate.model_fields.keys()) == expected

    def test_extra_fields_forbidden(self):
        """MeetingCreate uses extra='forbid'."""
        with pytest.raises(ValidationError):
            MeetingCreate(
                platform="google_meet",
                native_meeting_id="abc-defg-hij",
                unknown_field="oops",
            )


# ===================================================================
# 4. GET /recordings/{id}  →  RecordingResponse
# ===================================================================

class TestRecordingResponseContract:

    SAMPLE_MEDIA = {
        "id": 1,
        "type": "audio",
        "format": "wav",
        "storage_backend": "minio",
        "file_size_bytes": 1024000,
        "duration_seconds": 60.5,
        "extra_metadata": {"sample_rate": 16000},
        "created_at": "2025-06-01T10:05:00",
    }

    SAMPLE_RECORDING = {
        "id": 10,
        "meeting_id": 1,
        "user_id": 5,
        "session_uid": "sess-abc123",
        "source": "bot",
        "status": "completed",
        "error_message": None,
        "created_at": "2025-06-01T10:00:00",
        "completed_at": "2025-06-01T10:05:00",
        "media_files": [],
    }

    def test_recording_response_fields(self):
        expected = {
            "id", "meeting_id", "user_id", "session_uid", "source",
            "status", "error_message", "created_at", "completed_at",
            "media_files",
        }
        assert set(RecordingResponse.model_fields.keys()) == expected

    def test_recording_with_media(self):
        rec = RecordingResponse(**{
            **self.SAMPLE_RECORDING,
            "media_files": [self.SAMPLE_MEDIA],
        })
        assert len(rec.media_files) == 1
        assert rec.media_files[0].type == "audio"

    def test_media_file_fields(self):
        expected = {
            "id", "type", "format", "storage_backend",
            "file_size_bytes", "duration_seconds", "metadata",
            "created_at",
        }
        assert set(MediaFileResponse.model_fields.keys()) == expected

    def test_recording_status_values(self):
        expected = {"in_progress", "uploading", "completed", "failed"}
        assert {s.value for s in RecordingStatus} == expected

    def test_recording_source_values(self):
        expected = {"bot", "upload", "url"}
        assert {s.value for s in RecordingSource} == expected

    def test_media_file_type_values(self):
        expected = {"audio", "video", "screenshot"}
        assert {t.value for t in MediaFileType} == expected

    def test_recording_list_response(self):
        resp = RecordingListResponse(recordings=[
            RecordingResponse(**self.SAMPLE_RECORDING),
        ])
        assert len(resp.recordings) == 1


# ===================================================================
# 5. Voice Agent / Chat schemas
# ===================================================================

class TestVoiceAgentSchemaContract:

    def test_speak_request_fields(self):
        expected = {
            "text", "audio_url", "audio_base64", "format",
            "sample_rate", "provider", "voice",
        }
        assert set(SpeakRequest.model_fields.keys()) == expected

    def test_chat_message_fields(self):
        expected = {"sender", "text", "timestamp", "is_from_bot"}
        assert set(ChatMessage.model_fields.keys()) == expected
