"""Tests for auth module — API key validation and token scope checking."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from .conftest import make_user, make_token, TEST_API_KEY, TEST_USER_ID, MockResult


# ===================================================================
# get_api_key
# ===================================================================


class TestGetApiKey:

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_403(self):
        """No X-API-Key header → 403."""
        from meeting_api.auth import get_api_key

        db = AsyncMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_api_key(api_key=None, db=db)
        assert exc_info.value.status_code == 403
        assert "Missing" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_token_raises_403(self):
        """Token not in DB → 403."""
        from meeting_api.auth import get_api_key

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MockResult([]))

        with patch("meeting_api.auth.check_token_scope", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await get_api_key(api_key="invalid-key", db=db)
        assert exc_info.value.status_code == 403
        assert "Invalid" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_token_returns_tuple(self):
        """Valid token → returns (api_key, User)."""
        from meeting_api.auth import get_api_key

        user = make_user()
        token = make_token()

        # Simulate SQLAlchemy row: result.first() returns a tuple-like
        class FakeRow:
            def __init__(self, items):
                self._items = items
            def __getitem__(self, idx):
                return self._items[idx]

        result = MagicMock()
        result.first.return_value = FakeRow([token, user])
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result)

        with patch("meeting_api.auth.check_token_scope", return_value=True):
            api_key, returned_user = await get_api_key(api_key=TEST_API_KEY, db=db)

        assert api_key == TEST_API_KEY
        assert returned_user.id == TEST_USER_ID

    @pytest.mark.asyncio
    async def test_invalid_scope_raises_403(self):
        """Token with wrong scope → 403."""
        from meeting_api.auth import get_api_key

        db = AsyncMock()
        with patch("meeting_api.auth.check_token_scope", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await get_api_key(api_key="vxa_tx_somekey", db=db)
        assert exc_info.value.status_code == 403
        assert "scope" in exc_info.value.detail.lower()


# ===================================================================
# Auth via HTTP endpoints (integration-style)
# ===================================================================


class TestAuthViaEndpoints:

    @pytest.mark.asyncio
    async def test_no_api_key_header(self, unauthed_client):
        """Request without X-API-Key → 403 on any protected endpoint."""
        resp = await unauthed_client.get("/bots/status")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_health_no_auth_needed(self, client):
        """GET /health does not require auth."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
