from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worship_bot.config import Settings, get_settings
from worship_bot.infrastructure.database import get_session
from worship_bot.infrastructure.models import UserRecord

bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(user_id: int, settings: Settings) -> str:
    secret = settings.jwt_secret
    if secret is None:
        raise RuntimeError("JWT_SECRET must be configured")
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.jwt_lifetime_minutes)
    return jwt.encode(
        {"sub": str(user_id), "iat": datetime.now(UTC), "exp": expires_at},
        secret.get_secret_value(),
        algorithm="HS256",
    )


def set_session_cookie(response: Response, user_id: int, settings: Settings) -> None:
    response.set_cookie(
        "access_token",
        create_access_token(user_id, settings),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.jwt_lifetime_minutes * 60,
    )


async def require_bot_service(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    configured_token = settings.bot_service_token
    if configured_token is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot service authentication is not configured",
        )
    if credentials is None or not hmac.compare_digest(
        credentials.credentials, configured_token.get_secret_value()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bot service credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_id(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> int:
    secret: SecretStr | None = settings.jwt_secret
    if secret is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Web authentication is not configured",
        )
    token = credentials.credentials if credentials else request.cookies.get("access_token")
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = jwt.decode(
            token,
            secret.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["sub", "iat", "exp"]},
        )
        user_id = int(claims["sub"])
    except (jwt.InvalidTokenError, TypeError, ValueError, KeyError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    exists = await session.scalar(select(UserRecord.id).where(UserRecord.id == user_id))
    if exists is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user_id
