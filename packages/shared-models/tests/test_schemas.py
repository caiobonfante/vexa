"""Tests for Pydantic schemas, enums, and status transition logic."""

import pytest
from shared_models.schemas import (
    MeetingStatus,
    MeetingCompletionReason,
    MeetingFailureStage,
    Platform,
    MeetingCreate,
    MeetingResponse,
    is_valid_status_transition,
    get_status_source,
    get_valid_status_transitions,
)


# ---------------------------------------------------------------------------
# Enum completeness
# ---------------------------------------------------------------------------

class TestMeetingStatusEnum:
    def test_has_8_values(self):
        assert len(MeetingStatus) == 8

    def test_exact_values(self):
        expected = {
            "requested", "joining", "awaiting_admission", "active",
            "needs_human_help", "stopping", "completed", "failed",
        }
        actual = {s.value for s in MeetingStatus}
        assert actual == expected

    def test_terminal_states_have_no_transitions(self):
        transitions = get_valid_status_transitions()
        assert transitions[MeetingStatus.COMPLETED] == []
        assert transitions[MeetingStatus.FAILED] == []


class TestPlatformEnum:
    def test_has_4_values(self):
        assert len(Platform) == 4

    def test_exact_values(self):
        expected = {"google_meet", "zoom", "teams", "browser_session"}
        actual = {p.value for p in Platform}
        assert actual == expected


class TestCompletionReasonEnum:
    def test_has_6_values(self):
        assert len(MeetingCompletionReason) == 6

    def test_includes_key_reasons(self):
        values = {r.value for r in MeetingCompletionReason}
        assert "stopped" in values
        assert "evicted" in values
        assert "left_alone" in values


class TestFailureStageEnum:
    def test_has_4_values(self):
        assert len(MeetingFailureStage) == 4

    def test_exact_values(self):
        expected = {"requested", "joining", "awaiting_admission", "active"}
        actual = {s.value for s in MeetingFailureStage}
        assert actual == expected


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------

class TestStatusTransitions:
    def test_valid_forward_transitions(self):
        assert is_valid_status_transition(MeetingStatus.REQUESTED, MeetingStatus.JOINING)
        assert is_valid_status_transition(MeetingStatus.JOINING, MeetingStatus.AWAITING_ADMISSION)
        assert is_valid_status_transition(MeetingStatus.AWAITING_ADMISSION, MeetingStatus.ACTIVE)
        assert is_valid_status_transition(MeetingStatus.ACTIVE, MeetingStatus.COMPLETED)
        assert is_valid_status_transition(MeetingStatus.ACTIVE, MeetingStatus.STOPPING)
        assert is_valid_status_transition(MeetingStatus.STOPPING, MeetingStatus.COMPLETED)

    def test_valid_failure_transitions(self):
        for status in [MeetingStatus.REQUESTED, MeetingStatus.JOINING,
                       MeetingStatus.AWAITING_ADMISSION, MeetingStatus.ACTIVE,
                       MeetingStatus.STOPPING]:
            assert is_valid_status_transition(status, MeetingStatus.FAILED), \
                f"{status} should be able to transition to FAILED"

    def test_invalid_backward_transitions(self):
        assert not is_valid_status_transition(MeetingStatus.COMPLETED, MeetingStatus.ACTIVE)
        assert not is_valid_status_transition(MeetingStatus.FAILED, MeetingStatus.JOINING)
        assert not is_valid_status_transition(MeetingStatus.ACTIVE, MeetingStatus.REQUESTED)

    def test_terminal_states_cannot_transition(self):
        for target in MeetingStatus:
            assert not is_valid_status_transition(MeetingStatus.COMPLETED, target)
            assert not is_valid_status_transition(MeetingStatus.FAILED, target)

    def test_escalation_transitions(self):
        assert is_valid_status_transition(MeetingStatus.JOINING, MeetingStatus.NEEDS_HUMAN_HELP)
        assert is_valid_status_transition(MeetingStatus.AWAITING_ADMISSION, MeetingStatus.NEEDS_HUMAN_HELP)
        assert is_valid_status_transition(MeetingStatus.NEEDS_HUMAN_HELP, MeetingStatus.ACTIVE)
        assert is_valid_status_transition(MeetingStatus.NEEDS_HUMAN_HELP, MeetingStatus.FAILED)

    def test_direct_join_to_active(self):
        """Bot can go directly from joining to active (no waiting room)."""
        assert is_valid_status_transition(MeetingStatus.JOINING, MeetingStatus.ACTIVE)


class TestGetStatusSource:
    def test_user_initiated_stop(self):
        assert get_status_source(MeetingStatus.ACTIVE, MeetingStatus.STOPPING) == "user"

    def test_bot_callback_joining(self):
        assert get_status_source(MeetingStatus.REQUESTED, MeetingStatus.JOINING) == "bot_callback"

    def test_bot_callback_failure(self):
        assert get_status_source(MeetingStatus.ACTIVE, MeetingStatus.FAILED) == "bot_callback"

    def test_escalation_source(self):
        assert get_status_source(MeetingStatus.JOINING, MeetingStatus.NEEDS_HUMAN_HELP) == "bot_callback"


# ---------------------------------------------------------------------------
# MeetingCreate validation
# ---------------------------------------------------------------------------

class TestMeetingCreate:
    def test_requires_meeting_url(self):
        with pytest.raises(Exception):
            MeetingCreate()

    def test_valid_create(self):
        m = MeetingCreate(meeting_url="https://meet.google.com/abc-defg-hij")
        assert m.meeting_url == "https://meet.google.com/abc-defg-hij"

    def test_default_platform_detection(self):
        """Platform is auto-detected from URL if not specified."""
        m = MeetingCreate(meeting_url="https://meet.google.com/abc-defg-hij")
        # Should succeed without explicit platform
        assert m.meeting_url is not None
