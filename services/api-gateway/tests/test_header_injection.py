"""Tests for gateway header injection (Phase B).

Verifies:
- Valid X-API-Key -> downstream gets X-User-ID/X-User-Scopes/X-User-Limits
- Invalid X-API-Key -> downstream gets X-API-Key only (backward compat)
- Spoofed X-User-ID stripped before forwarding
- Cache hit -> admin-api not called twice for same token
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

# conftest.py sets env vars and sys.path
from main import app, forward_request, _resolve_token


def _make_request(headers: dict = None, body: bytes = b""):
    """Create a mock Starlette Request."""
    req = AsyncMock()
    req.headers = httpx.Headers(headers or {})
    req.query_params = {}
    req.body = AsyncMock(return_value=body)
    return req


def _make_validate_response(status_code=200, user_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = user_data or {}
    return resp


class TestHeaderStripping:
    """Spoofed identity headers are stripped before forwarding."""

    @pytest.mark.asyncio
    async def test_strips_spoofed_x_user_id(self):
        """Client-supplied X-User-ID is removed."""
        captured_headers = {}

        async def mock_request(method, url, headers=None, params=None, content=None):
            captured_headers.update(headers or {})
            resp = MagicMock()
            resp.content = b"{}"
            resp.status_code = 200
            resp.headers = {}
            return resp

        client = AsyncMock()
        client.request = mock_request
        client.post = AsyncMock(return_value=_make_validate_response(500))

        req = _make_request(headers={
            "x-api-key": "test_key",
            "x-user-id": "SPOOFED_999",
            "x-user-scopes": "admin",
            "x-user-limits": "100",
        })

        await forward_request(client, "GET", "http://bot-manager:8000/bots", req)

        assert captured_headers.get("x-user-id") != "SPOOFED_999"
        assert "x-user-scopes" not in captured_headers or captured_headers["x-user-scopes"] != "admin"
        assert "x-user-limits" not in captured_headers or captured_headers["x-user-limits"] != "100"


class TestHeaderInjection:
    """Valid tokens produce X-User-ID/X-User-Scopes/X-User-Limits headers."""

    @pytest.mark.asyncio
    async def test_valid_token_injects_headers(self):
        """Successful validation injects identity headers."""
        captured_headers = {}
        user_data = {"user_id": 5, "scopes": ["bot"], "max_concurrent": 3, "email": "test@x.com"}

        async def mock_request(method, url, headers=None, params=None, content=None):
            captured_headers.update(headers or {})
            resp = MagicMock()
            resp.content = b"{}"
            resp.status_code = 200
            resp.headers = {}
            return resp

        client = AsyncMock()
        client.request = mock_request
        client.post = AsyncMock(return_value=_make_validate_response(200, user_data))

        # No Redis in test
        app.state.redis = None

        req = _make_request(headers={"x-api-key": "vxa_bot_abc123"})
        await forward_request(client, "GET", "http://bot-manager:8000/bots", req)

        assert captured_headers["x-user-id"] == "5"
        assert captured_headers["x-user-scopes"] == "bot"
        assert captured_headers["x-user-limits"] == "3"

    @pytest.mark.asyncio
    async def test_invalid_token_backward_compat(self):
        """Failed validation still forwards X-API-Key (no identity headers)."""
        captured_headers = {}

        async def mock_request(method, url, headers=None, params=None, content=None):
            captured_headers.update(headers or {})
            resp = MagicMock()
            resp.content = b"{}"
            resp.status_code = 200
            resp.headers = {}
            return resp

        client = AsyncMock()
        client.request = mock_request
        client.post = AsyncMock(return_value=_make_validate_response(401))

        app.state.redis = None

        req = _make_request(headers={"x-api-key": "bad_token"})
        await forward_request(client, "GET", "http://bot-manager:8000/bots", req)

        assert captured_headers.get("x-api-key") == "bad_token"
        assert "x-user-id" not in captured_headers


class TestTokenCache:
    """Redis cache prevents repeated admin-api calls."""

    @pytest.mark.asyncio
    async def test_cache_hit_skips_admin_api(self):
        """Cached token data means admin-api is NOT called."""
        user_data = {"user_id": 7, "scopes": ["user"], "max_concurrent": 1, "email": "cached@x.com"}

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(user_data))
        app.state.redis = mock_redis

        client = AsyncMock()
        # client.post should NOT be called if cache hit
        client.post = AsyncMock()

        result = await _resolve_token(client, "vxa_user_cachedtoken123")

        assert result == user_data
        client.post.assert_not_called()
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_miss_calls_admin_api_and_caches(self):
        """Cache miss calls admin-api and stores result."""
        user_data = {"user_id": 7, "scopes": ["user"], "max_concurrent": 1, "email": "new@x.com"}

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        app.state.redis = mock_redis

        client = AsyncMock()
        client.post = AsyncMock(return_value=_make_validate_response(200, user_data))

        result = await _resolve_token(client, "vxa_user_newtoken12345")

        assert result == user_data
        client.post.assert_called_once()
        mock_redis.set.assert_called_once()
        # Verify TTL is 60 seconds
        call_args = mock_redis.set.call_args
        assert call_args.kwargs.get("ex") == 60 or (len(call_args.args) >= 3 and call_args.args[2] == 60) or call_args[1].get("ex") == 60
