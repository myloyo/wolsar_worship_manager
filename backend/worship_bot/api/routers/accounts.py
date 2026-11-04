import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from worship_bot.api.membership_schemas import AccountConnections, AccountLinkCreate, BotAccountLink
from worship_bot.api.routers.portal import Configuration, CurrentUser, Session
from worship_bot.api.security import require_bot_service
from worship_bot.infrastructure.models import AccountLinkRecord, ExternalAccountRecord, UserRecord
from worship_bot.infrastructure.repositories.portal import SqlPortalRepository

router = APIRouter(prefix="/portal/me", tags=["linked accounts"])
internal_router = APIRouter(
    prefix="/internal/bot", tags=["linked accounts"], dependencies=[Depends(require_bot_service)]
)


@router.get("/accounts", response_model=AccountConnections)
async def connections(user_id: CurrentUser, session: Session) -> AccountConnections:
    record = await session.scalar(
        select(ExternalAccountRecord).where(
            ExternalAccountRecord.user_id == user_id, ExternalAccountRecord.provider == "telegram"
        )
    )
    return AccountConnections(
        telegram_linked=record is not None, telegram_username=record.username if record else None
    )


@router.post("/telegram-link", response_model=AccountLinkCreate)
async def issue_link(user_id: CurrentUser, session: Session) -> AccountLinkCreate:
    if (await connections(user_id, session)).telegram_linked:
        raise HTTPException(409, "Telegram уже привязан к этому аккаунту")
    now = datetime.now(UTC)
    await session.execute(
        update(AccountLinkRecord)
        .where(
            AccountLinkRecord.user_id == user_id,
            AccountLinkRecord.provider == "telegram",
            AccountLinkRecord.used_at.is_(None),
        )
        .values(used_at=now)
    )
    code = secrets.token_urlsafe(24)
    expires_at = now + timedelta(minutes=10)
    session.add(
        AccountLinkRecord(
            code_hash=hashlib.sha256(code.encode()).hexdigest(),
            user_id=user_id,
            provider="telegram",
            expires_at=expires_at,
        )
    )
    await session.commit()
    return AccountLinkCreate(
        url="https://t.me/wolsar_worship_bot?start=link_" + quote(code), expires_at=expires_at
    )


@internal_router.post("/link")
async def complete_link(
    payload: BotAccountLink, session: Session, settings: Configuration
) -> dict[str, str]:
    now = datetime.now(UTC)
    record = await session.scalar(
        select(AccountLinkRecord)
        .where(
            AccountLinkRecord.code_hash == hashlib.sha256(payload.code.encode()).hexdigest(),
            AccountLinkRecord.provider == payload.provider.value,
            AccountLinkRecord.used_at.is_(None),
            AccountLinkRecord.expires_at > now,
        )
        .with_for_update()
    )
    if record is None:
        raise HTTPException(
            409, "Ссылка привязки устарела или уже использована. Создайте новую в личной карточке"
        )
    await session.scalar(
        select(UserRecord).where(UserRecord.id == record.user_id).with_for_update()
    )
    owner = await session.scalar(
        select(ExternalAccountRecord).where(
            ExternalAccountRecord.provider == payload.provider.value,
            ExternalAccountRecord.external_user_id == payload.external_user_id,
        )
    )
    current = await session.scalar(
        select(ExternalAccountRecord).where(
            ExternalAccountRecord.provider == payload.provider.value,
            ExternalAccountRecord.user_id == record.user_id,
        )
    )
    if owner is not None and owner.user_id != record.user_id:
        raise HTTPException(409, "Этот Telegram уже связан с другим аккаунтом")
    if current is not None and current.external_user_id != payload.external_user_id:
        raise HTTPException(409, "В аккаунте уже привязан другой Telegram")
    if current is None:
        session.add(
            ExternalAccountRecord(
                user_id=record.user_id,
                provider=payload.provider.value,
                external_user_id=payload.external_user_id,
                username=payload.username,
                verified_at=now,
            )
        )
    record.used_at = now
    user_id = record.user_id
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(409, "Telegram уже привязан к другому аккаунту") from error
    ticket = await SqlPortalRepository(session).issue_login(user_id)
    return {"url": settings.web_url.rstrip("/") + "/#code=" + quote(ticket.code)}
