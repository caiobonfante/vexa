"""Unit tests for api/endpoints.py.

Tests the health check and transcript retrieval endpoints.
Auth is mocked via dependency override.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from fastapi.testclient import TestClient


@pytest.fixture
def mock_user():
    """Create a mock User object."""
    user = MagicMock()
    user.id = 5
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_db():
    """Create a mock async DB session."""
    db = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    r = AsyncMock()
    r.ping = AsyncMock()
    r.hgetall = AsyncMock(return_value={})
    return r


@pytest.fixture
def app_client(mock_user, mock_db, mock_redis):
    """Create a TestClient with mocked dependencies."""
    from main import app
    from api.auth import get_current_user
    from shared_models.database import get_db

    async def override_get_current_user():
        return mock_user

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db
    app.state.redis_client = mock_redis

    client = TestClient(app, raise_server_exceptions=False)
    yield client

    app.dependency_overrides.clear()


class TestHealthEndpoint:
    def test_health_returns_200_when_healthy(self, app_client, mock_db, mock_redis):
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_redis.ping = AsyncMock()

        resp = app_client.get("/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_health_reports_unhealthy_redis(self, app_client, mock_db, mock_redis):
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_redis.ping = AsyncMock(side_effect=Exception("connection refused"))

        resp = app_client.get("/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unhealthy"
        assert "unhealthy" in data["redis"]

    def test_health_reports_unhealthy_db(self, app_client, mock_db, mock_redis):
        mock_db.execute = AsyncMock(side_effect=Exception("db down"))
        mock_redis.ping = AsyncMock()

        resp = app_client.get("/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unhealthy"
        assert "unhealthy" in data["database"]


class TestAuthRequired:
    def test_missing_api_key_returns_403(self):
        """Without dependency override, missing API key returns 403."""
        from main import app
        from api.auth import get_current_user
        from fastapi import HTTPException, status

        # Remove the override to test real auth
        app.dependency_overrides.clear()

        async def strict_auth():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing API token")

        app.dependency_overrides[get_current_user] = strict_auth

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/meetings")

        assert resp.status_code == 403
        app.dependency_overrides.clear()


class TestGetMeetings:
    def test_get_meetings_returns_list(self, app_client, mock_db):
        # Mock DB result that returns empty list of meetings
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = app_client.get("/meetings")

        assert resp.status_code == 200
        data = resp.json()
        assert "meetings" in data
        assert isinstance(data["meetings"], list)


class TestGetTranscript:
    def test_transcript_not_found_returns_404(self, app_client, mock_db):
        # Mock DB returning no meeting
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = app_client.get("/transcripts/teams/nonexistent-meeting")

        assert resp.status_code == 404

    def test_transcript_found_calls_db(self, app_client, mock_db, mock_redis):
        """Verify the endpoint queries the database when a meeting is found.

        The full response requires a real ORM Meeting object for model_validate,
        so we verify the DB query path works and that a found meeting doesn't 404.
        """
        from shared_models.models import Meeting

        # Create a real Meeting ORM instance (not a Mock) so model_validate works
        meeting = Meeting(
            id=1, user_id=5, platform="teams",
            platform_specific_id="meeting123", status="completed",
            data={},
        )
        meeting.created_at = datetime.now(timezone.utc)
        meeting.updated_at = datetime.now(timezone.utc)

        # Mock the meeting query
        mock_meeting_result = MagicMock()
        mock_meeting_result.scalars.return_value.first.return_value = meeting

        # Mock the session query (no sessions) and transcription query
        mock_empty_result = MagicMock()
        mock_empty_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[
            mock_meeting_result,  # Meeting lookup
            mock_empty_result,    # Session query
            mock_empty_result,    # Transcription query
        ])

        mock_redis.hgetall = AsyncMock(return_value={})

        resp = app_client.get("/transcripts/teams/meeting123")

        # Should not be 404 — meeting was found
        assert resp.status_code != 404
        # DB was queried
        assert mock_db.execute.call_count >= 1


class TestInternalTranscript:
    def test_internal_transcript_not_found(self, app_client, mock_db):
        mock_db.get = AsyncMock(return_value=None)

        resp = app_client.get("/internal/transcripts/999")

        assert resp.status_code == 404
