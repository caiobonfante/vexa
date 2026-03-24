"""Simple API key authentication for chat-api.

Validates X-API-Key header against BOT_API_TOKEN env var.
This avoids needing a database connection in chat-api while still
preventing unauthenticated access. The token is the same one used
for service-to-service auth (chat-api -> runtime-api).
"""

import hmac
import logging
import os

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger("agent_api.auth")

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
_API_TOKEN = os.getenv("BOT_API_TOKEN", "")


async def require_api_key(api_key: str = Security(API_KEY_HEADER)):
    """FastAPI dependency that rejects requests without a valid API key."""
    if not _API_TOKEN:
        logger.error("BOT_API_TOKEN not configured — rejecting all requests")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication not configured",
        )
    if not api_key or not hmac.compare_digest(api_key, _API_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key",
        )
