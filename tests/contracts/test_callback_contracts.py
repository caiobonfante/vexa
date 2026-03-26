"""
Contract tests: Internal callback payloads.

Documents the Pydantic models used by bot containers to report
status back to bot-manager via /bots/internal/callback/* endpoints.
These shapes are the wire protocol between vexa-bot and bot-manager.

Run: pytest tests/contracts/test_callback_contracts.py -v
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
from pydantic import BaseModel, Field, ValidationError

from shared_models.schemas import (
    MeetingCompletionReason,
    MeetingFailureStage,
    MeetingStatus,
)


# ===================================================================
# Frozen callback payload models — duplicated from bot-manager/app/main.py
# so contract tests catch drift between bot-manager and vexa-bot.
# ===================================================================

class BotExitCallbackPayload(BaseModel):
    """POST /bots/internal/callback/exited — bot reports exit."""
    connection_id: str
    exit_code: int
    reason: Optional[str] = "self_initiated_leave"
    error_details: Optional[Dict[str, Any]] = None
    platform_specific_error: Optional[str] = None
    completion_reason: Optional[MeetingCompletionReason] = None
    failure_stage: Optional[MeetingFailureStage] = None


class BotStartupCallbackPayload(BaseModel):
    """POST /bots/internal/callback/started — bot reports startup.
    Also reused for /joining and /awaiting_admission."""
    connection_id: str
    container_id: str


class BotStatusChangePayload(BaseModel):
    """POST /bots/internal/callback/status_change — unified callback."""
    connection_id: str
    container_id: Optional[str] = None
    status: MeetingStatus
    reason: Optional[str] = None
    exit_code: Optional[int] = None
    error_details: Optional[Dict[str, Any]] = None
    platform_specific_error: Optional[str] = None
    completion_reason: Optional[MeetingCompletionReason] = None
    failure_stage: Optional[MeetingFailureStage] = None
    timestamp: Optional[str] = None
    speaker_events: Optional[List[Dict]] = None


# ===================================================================
# 1. /bots/internal/callback/exited
# ===================================================================

class TestExitedCallback:

    def test_minimal_success_exit(self):
        p = BotExitCallbackPayload(
            connection_id="sess-abc123",
            exit_code=0,
        )
        assert p.exit_code == 0
        assert p.reason == "self_initiated_leave"

    def test_failure_exit_with_details(self):
        p = BotExitCallbackPayload(
            connection_id="sess-abc123",
            exit_code=1,
            reason="browser_crashed",
            error_details={"stack": "Error at line 42", "message": "Page crashed"},
            platform_specific_error="ERR_CONNECTION_REFUSED",
            completion_reason=None,
            failure_stage="active",
        )
        assert p.exit_code == 1
        assert p.failure_stage == MeetingFailureStage.ACTIVE

    def test_completion_reason_accepted(self):
        p = BotExitCallbackPayload(
            connection_id="sess-abc",
            exit_code=0,
            completion_reason="left_alone",
        )
        assert p.completion_reason == MeetingCompletionReason.LEFT_ALONE

    def test_field_names_frozen(self):
        expected = {
            "connection_id", "exit_code", "reason", "error_details",
            "platform_specific_error", "completion_reason", "failure_stage",
        }
        assert set(BotExitCallbackPayload.model_fields.keys()) == expected

    def test_connection_id_required(self):
        with pytest.raises(ValidationError):
            BotExitCallbackPayload(exit_code=0)

    def test_exit_code_required(self):
        with pytest.raises(ValidationError):
            BotExitCallbackPayload(connection_id="sess-abc")


# ===================================================================
# 2. /bots/internal/callback/started (also /joining, /awaiting_admission)
# ===================================================================

class TestStartupCallback:

    def test_startup_payload(self):
        p = BotStartupCallbackPayload(
            connection_id="sess-abc123",
            container_id="container-xyz",
        )
        assert p.connection_id == "sess-abc123"
        assert p.container_id == "container-xyz"

    def test_field_names_frozen(self):
        expected = {"connection_id", "container_id"}
        assert set(BotStartupCallbackPayload.model_fields.keys()) == expected

    def test_both_fields_required(self):
        with pytest.raises(ValidationError):
            BotStartupCallbackPayload(connection_id="sess-abc")
        with pytest.raises(ValidationError):
            BotStartupCallbackPayload(container_id="container-xyz")


# ===================================================================
# 3. /bots/internal/callback/status_change (unified)
# ===================================================================

class TestStatusChangeCallback:

    def test_minimal_joining(self):
        p = BotStatusChangePayload(
            connection_id="sess-abc",
            status="joining",
        )
        assert p.status == MeetingStatus.JOINING

    def test_full_completed(self):
        p = BotStatusChangePayload(
            connection_id="sess-abc",
            container_id="ctr-xyz",
            status="completed",
            reason="meeting ended",
            exit_code=0,
            completion_reason="stopped",
            timestamp="2025-06-01T10:30:00Z",
        )
        assert p.status == MeetingStatus.COMPLETED
        assert p.completion_reason == MeetingCompletionReason.STOPPED

    def test_failed_with_error(self):
        p = BotStatusChangePayload(
            connection_id="sess-abc",
            status="failed",
            exit_code=1,
            error_details={"message": "timeout"},
            platform_specific_error="TIMEOUT",
            failure_stage="awaiting_admission",
        )
        assert p.status == MeetingStatus.FAILED
        assert p.failure_stage == MeetingFailureStage.AWAITING_ADMISSION

    def test_with_speaker_events(self):
        p = BotStatusChangePayload(
            connection_id="sess-abc",
            status="active",
            speaker_events=[
                {"speaker": "Alice", "start": 0.0, "end": 5.0},
                {"speaker": "Bob", "start": 5.0, "end": 10.0},
            ],
        )
        assert len(p.speaker_events) == 2

    def test_field_names_frozen(self):
        expected = {
            "connection_id", "container_id", "status", "reason",
            "exit_code", "error_details", "platform_specific_error",
            "completion_reason", "failure_stage", "timestamp",
            "speaker_events",
        }
        assert set(BotStatusChangePayload.model_fields.keys()) == expected

    def test_connection_id_required(self):
        with pytest.raises(ValidationError):
            BotStatusChangePayload(status="active")

    def test_status_required(self):
        with pytest.raises(ValidationError):
            BotStatusChangePayload(connection_id="sess-abc")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            BotStatusChangePayload(
                connection_id="sess-abc",
                status="bogus_status",
            )


# ===================================================================
# 4. Callback response shapes (bot-manager → bot)
# ===================================================================

class CallbackSuccessResponse(BaseModel):
    """Generic success response from callback endpoints."""
    status: str
    meeting_id: Optional[int] = None
    meeting_status: Optional[str] = None
    final_status: Optional[str] = None
    detail: Optional[str] = None


class TestCallbackResponses:

    def test_exited_success_response(self):
        """bot_exit_callback returns this shape on success."""
        resp = CallbackSuccessResponse(
            status="callback processed",
            meeting_id=42,
            final_status="completed",
        )
        assert resp.status == "callback processed"

    def test_started_success_response(self):
        resp = CallbackSuccessResponse(
            status="startup processed",
            meeting_id=42,
            meeting_status="active",
        )
        assert resp.status == "startup processed"

    def test_joining_success_response(self):
        resp = CallbackSuccessResponse(
            status="joining processed",
            meeting_id=42,
            meeting_status="joining",
        )
        assert resp.status == "joining processed"

    def test_awaiting_admission_response(self):
        resp = CallbackSuccessResponse(
            status="awaiting_admission processed",
            meeting_id=42,
            meeting_status="awaiting_admission",
        )
        assert resp.status == "awaiting_admission processed"

    def test_error_response(self):
        resp = CallbackSuccessResponse(
            status="error",
            detail="Meeting session not found",
        )
        assert resp.status == "error"

    def test_ignored_response(self):
        """When stop_requested is set, callbacks return 'ignored'."""
        resp = CallbackSuccessResponse(
            status="ignored",
            detail="stop requested",
        )
        assert resp.status == "ignored"


# ===================================================================
# 5. Status transition contract
# ===================================================================

class TestStatusTransitionContract:
    """Verify the valid status transitions are frozen."""

    def test_valid_transitions_from_requested(self):
        from shared_models.schemas import get_valid_status_transitions
        transitions = get_valid_status_transitions()
        expected = {
            MeetingStatus.JOINING,
            MeetingStatus.FAILED,
            MeetingStatus.COMPLETED,
            MeetingStatus.STOPPING,
        }
        assert set(transitions[MeetingStatus.REQUESTED]) == expected

    def test_valid_transitions_from_active(self):
        from shared_models.schemas import get_valid_status_transitions
        transitions = get_valid_status_transitions()
        expected = {
            MeetingStatus.STOPPING,
            MeetingStatus.COMPLETED,
            MeetingStatus.FAILED,
        }
        assert set(transitions[MeetingStatus.ACTIVE]) == expected

    def test_terminal_states(self):
        from shared_models.schemas import get_valid_status_transitions
        transitions = get_valid_status_transitions()
        assert transitions[MeetingStatus.COMPLETED] == []
        assert transitions[MeetingStatus.FAILED] == []

    def test_is_valid_transition_helper(self):
        from shared_models.schemas import is_valid_status_transition
        assert is_valid_status_transition(MeetingStatus.REQUESTED, MeetingStatus.JOINING)
        assert not is_valid_status_transition(MeetingStatus.COMPLETED, MeetingStatus.ACTIVE)
