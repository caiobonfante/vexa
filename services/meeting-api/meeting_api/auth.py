"""API key validation — same logic as bot-manager/app/auth.py."""

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import logging

from shared_models.models import User, APIToken
from shared_models.database import get_db
from shared_models.token_scope import check_token_scope

logger = logging.getLogger("meeting_api.auth")

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(
    api_key: str = Security(API_KEY_HEADER),
    db: AsyncSession = Depends(get_db),
) -> tuple[str, User]:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing API token (X-API-Key header)",
        )

    if not check_token_scope(api_key, {"bot", "user", "admin"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token scope not authorized for bot management",
        )

    result = await db.execute(
        select(APIToken, User)
        .join(User, APIToken.user_id == User.id)
        .where(APIToken.token == api_key)
    )
    token_user = result.first()

    if not token_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API token",
        )

    user_obj = token_user[1]
    if not isinstance(user_obj, User):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication data error",
        )

    return (api_key, user_obj)


async def get_user_and_token(
    token_user_tuple: tuple[str, User] = Depends(get_api_key),
) -> tuple[str, User]:
    if not isinstance(token_user_tuple, tuple) or len(token_user_tuple) != 2:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication processing error",
        )
    return token_user_tuple
