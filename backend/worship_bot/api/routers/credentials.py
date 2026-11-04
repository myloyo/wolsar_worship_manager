import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from worship_bot.api.credential_schemas import (
    CredentialsRead,
    CredentialsUpdate,
    PasswordLogin,
    SiteRegistration,
)
from worship_bot.api.routers.portal import Configuration, CurrentUser, Session
from worship_bot.api.security import set_session_cookie
from worship_bot.infrastructure.models import (
    ConsentAcceptanceRecord,
    UserRecord,
    WebCredentialRecord,
)
from worship_bot.infrastructure.passwords import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["web login"])


@router.get("/credentials", response_model=CredentialsRead)
async def credentials(user_id: CurrentUser, session: Session) -> CredentialsRead:
    record = await session.get(WebCredentialRecord, user_id)
    return CredentialsRead(login=record.login if record else None, has_password=record is not None)


@router.put("/credentials", response_model=CredentialsRead)
async def set_credentials(
    payload: CredentialsUpdate, user_id: CurrentUser, session: Session
) -> CredentialsRead:
    record = await session.scalar(
        select(WebCredentialRecord).where(WebCredentialRecord.user_id == user_id).with_for_update()
    )
    if record is not None:
        current = payload.current_password.get_secret_value() if payload.current_password else ""
        if not await asyncio.to_thread(verify_password, current, record.password_hash):
            raise HTTPException(403, "Текущий пароль указан неверно")
    hashed = await asyncio.to_thread(hash_password, payload.password.get_secret_value())
    if record is None:
        record = WebCredentialRecord(user_id=user_id, login=payload.login, password_hash=hashed)
        session.add(record)
    else:
        record.login, record.password_hash = payload.login, hashed
        record.failed_attempts, record.locked_until = 0, None
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(409, "Этот логин уже занят") from error
    return CredentialsRead(login=record.login, has_password=True)


@router.post("/login")
async def password_login(
    payload: PasswordLogin,
    session: Session,
    settings: Configuration,
    response: Response,
) -> dict[str, str]:
    record = await session.scalar(
        select(WebCredentialRecord)
        .where(WebCredentialRecord.login == payload.login)
        .with_for_update()
    )
    now = datetime.now(UTC)
    if record is not None and record.locked_until is not None:
        if record.locked_until.replace(tzinfo=UTC) > now:
            raise HTTPException(429, "Слишком много попыток. Повторите вход через 5 минут")
        record.failed_attempts, record.locked_until = 0, None
    valid = await asyncio.to_thread(
        verify_password,
        payload.password.get_secret_value(),
        record.password_hash if record else None,
    )
    if not valid or record is None:
        if record is not None:
            record.failed_attempts += 1
            if record.failed_attempts >= 5:
                record.locked_until = now + timedelta(minutes=5)
            await session.commit()
        raise HTTPException(401, "Неверный логин или пароль")
    record.failed_attempts, record.locked_until = 0, None
    await session.commit()
    set_session_cookie(response, record.user_id, settings)
    return {"status": "authenticated"}


@router.post("/register", status_code=201)
async def register(
    payload: SiteRegistration, session: Session, settings: Configuration, response: Response
) -> dict[str, str]:
    hashed = await asyncio.to_thread(hash_password, payload.password.get_secret_value())
    user = UserRecord(
        name=payload.name,
        surname=payload.surname,
        church_id=None,
        consent_approved=True,
        system_role="member",
    )
    session.add(user)
    try:
        await session.flush()
        session.add(WebCredentialRecord(user_id=user.id, login=payload.login, password_hash=hashed))
        session.add(
            ConsentAcceptanceRecord(
                user_id=user.id,
                provider="web",
                policy_version=settings.registration_consent_version,
            )
        )
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(409, "Этот логин уже занят") from error
    set_session_cookie(response, user.id, settings)
    return {"status": "registered"}
