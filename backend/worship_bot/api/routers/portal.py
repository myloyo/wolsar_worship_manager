from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from worship_bot.api.handlers.events import create_event_series, map_calendar_item
from worship_bot.api.schemas import (
    AccessUpdate,
    BotIdentity,
    BotInvitationReply,
    EventCalendarItemRead,
    EventSeriesCreate,
    LoginExchange,
    LoginLinkRead,
    MemberRoleCreate,
    MinistryRoleCreate,
    PortalAssignment,
    PortalEventParticipant,
    ProfileUpdate,
)
from worship_bot.api.security import create_access_token, get_current_user_id, require_bot_service
from worship_bot.application.exceptions import (
    AccessDeniedError,
    MinistryRoleNotFoundError,
    ParticipantNotFoundError,
)
from worship_bot.application.services import EventCalendarService, MinistryService
from worship_bot.config import Settings, get_settings
from worship_bot.domain.portal import Member, Profile
from worship_bot.infrastructure.database import get_session
from worship_bot.infrastructure.models import (
    EventRecord,
    EventRoleSlotRecord,
    MinistryMembershipRecord,
    MinistryRoleRecord,
    NotificationJobRecord,
    UserMinistryRoleRecord,
    UserRecord,
)
from worship_bot.infrastructure.notification_queue import queue_event_reminders
from worship_bot.infrastructure.repositories.churches import SqlChurchRepository
from worship_bot.infrastructure.repositories.event_lifecycle import SqlEventLifecycleRepository
from worship_bot.infrastructure.repositories.event_preferences import require_role_eligible
from worship_bot.infrastructure.repositories.events import SqlEventCalendarRepository
from worship_bot.infrastructure.repositories.ministries import SqlMinistryRepository
from worship_bot.infrastructure.repositories.portal import SqlPortalRepository

router = APIRouter(tags=["portal"])
internal_router = APIRouter(
    prefix="/internal/bot", tags=["bot service"], dependencies=[Depends(require_bot_service)]
)
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[int, Depends(get_current_user_id)]
Configuration = Annotated[Settings, Depends(get_settings)]


async def require_portal_permission(
    session: AsyncSession, user_id: int, ministry_id: int, permission: str
) -> None:
    try:
        await SqlPortalRepository(session).require_permission(user_id, ministry_id, permission)
    except AccessDeniedError as error:
        raise HTTPException(403, str(error)) from error


@router.post("/auth/exchange")
async def exchange_login(
    payload: LoginExchange, session: Session, settings: Configuration, response: Response
) -> dict[str, str]:
    user_id = await SqlPortalRepository(session).exchange_login(payload.code)
    if user_id is None:
        raise HTTPException(401, "Ссылка устарела или уже использована")
    token = create_access_token(user_id, settings)
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.jwt_lifetime_minutes * 60,
    )
    return {"status": "authenticated"}


@router.post("/auth/logout", status_code=204)
async def logout(response: Response) -> None:
    response.delete_cookie("access_token")


@router.get("/portal/me", response_model=Profile)
async def me(user_id: CurrentUser, session: Session) -> Profile:
    return await SqlPortalRepository(session).profile(user_id)


@router.put("/portal/me", response_model=Profile)
async def update_me(payload: ProfileUpdate, user_id: CurrentUser, session: Session) -> Profile:
    user = await session.get(UserRecord, user_id)
    if user is None:
        raise HTTPException(404, "Пользователь не найден")
    user.name, user.surname, user.birthday_date = (
        payload.name,
        payload.surname,
        payload.birthday_date,
    )
    await session.commit()
    return await SqlPortalRepository(session).profile(user_id)


@router.get("/portal/ministries/{ministry_id}/members", response_model=list[Member])
async def members(ministry_id: int, user_id: CurrentUser, session: Session) -> list[Member]:
    await require_portal_permission(session, user_id, ministry_id, "view_members")
    return await SqlPortalRepository(session).members(ministry_id)


@router.get("/portal/ministries/{ministry_id}/events", response_model=list[EventCalendarItemRead])
async def calendar(
    ministry_id: int,
    user_id: CurrentUser,
    session: Session,
    start: Annotated[datetime, Query()],
    end: Annotated[datetime, Query()],
) -> list[EventCalendarItemRead]:
    await require_portal_permission(session, user_id, ministry_id, "view_schedule")
    if start.tzinfo is None or end.tzinfo is None or start >= end or (end - start).days > 100:
        raise HTTPException(422, "Укажите диапазон до 100 дней с часовым поясом")
    events = await EventCalendarService(SqlEventCalendarRepository(session)).list_events(
        start, end, ministry_id
    )
    return [map_calendar_item(event) for event in events if event.event.event_date < end]


@router.post("/portal/ministries/{ministry_id}/events", response_model=list[EventCalendarItemRead])
async def create_calendar_event(
    ministry_id: int, payload: EventSeriesCreate, user_id: CurrentUser, session: Session
) -> list[EventCalendarItemRead]:
    await require_portal_permission(session, user_id, ministry_id, "manage_events")
    return await create_event_series(
        ministry_id, payload, EventCalendarService(SqlEventCalendarRepository(session))
    )


@internal_router.post("/login", response_model=LoginLinkRead)
async def bot_login(
    payload: BotIdentity, session: Session, settings: Configuration
) -> LoginLinkRead:
    repository = SqlPortalRepository(session)
    user_id = await repository.external_user(payload.provider.value, payload.external_user_id)
    if user_id is None:
        raise HTTPException(
            404,
            "Telegram ещё не привязан. Войдите на сайт и откройте "
            "«Моя карточка → Привязать Telegram»",
        )
    ticket = await repository.issue_login(user_id)
    return LoginLinkRead(
        code=ticket.code,
        url=settings.web_url.rstrip("/") + "/#code=" + quote(ticket.code),
        expires_at=ticket.expires_at,
    )


@internal_router.post("/profile", response_model=Profile)
async def bot_profile(payload: BotIdentity, session: Session) -> Profile:
    repository = SqlPortalRepository(session)
    user_id = await repository.external_user(payload.provider.value, payload.external_user_id)
    if user_id is None:
        raise HTTPException(
            404,
            "Telegram ещё не привязан. Войдите на сайт и откройте "
            "«Моя карточка → Привязать Telegram»",
        )
    return await repository.profile(user_id)


@router.put("/portal/role-slots/{slot_id}")
async def assign_slot(
    slot_id: int, payload: PortalAssignment, user_id: CurrentUser, session: Session
) -> dict[str, str]:
    slot = await session.get(EventRoleSlotRecord, slot_id)
    if slot is None:
        raise HTTPException(404, "Роль не найдена")
    event = await session.scalar(
        select(EventRecord).where(EventRecord.id == slot.event_id).with_for_update()
    )
    await session.refresh(slot)
    if event is None or event.church_ministry_id is None:
        raise HTTPException(404, "Событие не найдено")
    await require_portal_permission(
        session, user_id, event.church_ministry_id, "manage_assignments"
    )
    previous_role_id = slot.user_ministry_role_id
    if payload.user_ministry_role_id is not None:
        try:
            await require_role_eligible(session, payload.user_ministry_role_id, event.event_kind)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        valid = await SqlEventCalendarRepository(session).user_ministry_role_matches(
            payload.user_ministry_role_id, slot.ministry_role_id
        )
        belongs = await SqlEventCalendarRepository(session).user_role_ids_belong_to(
            event.church_ministry_id, (payload.user_ministry_role_id,)
        )
        if not valid or not belongs:
            raise HTTPException(422, "Участник не имеет этой роли в служении")
    slot.user_ministry_role_id = payload.user_ministry_role_id
    slot.confirmation_status = "pending"
    for role_id, action in (
        (previous_role_id, "removed"),
        (payload.user_ministry_role_id, "assignment"),
    ):
        if role_id is None or previous_role_id == payload.user_ministry_role_id:
            continue
        recipient = await session.scalar(
            select(MinistryMembershipRecord.user_id)
            .join(
                UserMinistryRoleRecord,
                UserMinistryRoleRecord.ministry_membership_id == MinistryMembershipRecord.id,
            )
            .where(UserMinistryRoleRecord.id == role_id)
        )
        if recipient is not None:
            session.add(
                NotificationJobRecord(
                    event_id=event.id,
                    user_id=recipient,
                    notification_type=action,
                    scheduled_at=datetime.now(UTC),
                    payload={
                        "slot_id": slot.id,
                        "user_ministry_role_id": role_id,
                        "event_name": event.event_name,
                        "starts_at": event.event_date.isoformat(),
                    },
                    deduplication_key=str(uuid4()),
                )
            )
    await session.flush()
    await queue_event_reminders(session, event.id)
    await session.commit()
    return {"status": "updated"}


@router.put("/portal/ministries/{ministry_id}/members/{member_id}/access", status_code=204)
async def change_access(
    ministry_id: int, member_id: int, payload: AccessUpdate, user_id: CurrentUser, session: Session
) -> None:
    await require_portal_permission(session, user_id, ministry_id, "manage_members")
    try:
        await MinistryService(
            SqlMinistryRepository(session), SqlChurchRepository(session)
        ).set_member_access_level(user_id, ministry_id, member_id, payload.access_level)
    except PermissionError as error:
        raise HTTPException(403, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except LookupError as error:
        raise HTTPException(404, str(error)) from error


@internal_router.post("/schedule", response_model=list[EventCalendarItemRead])
async def bot_schedule(payload: BotIdentity, session: Session) -> list[EventCalendarItemRead]:
    repository = SqlPortalRepository(session)
    user_id = await repository.external_user(payload.provider.value, payload.external_user_id)
    if user_id is None:
        raise HTTPException(
            404,
            "Telegram ещё не привязан. Войдите на сайт и откройте "
            "«Моя карточка → Привязать Telegram»",
        )
    profile = await repository.profile(user_id)
    now = datetime.now(UTC)
    calendar_service = EventCalendarService(SqlEventCalendarRepository(session))
    result: list[EventCalendarItemRead] = []
    for ministry in profile.ministries:
        events = await calendar_service.list_events(now, now + timedelta(days=30), ministry.id)
        result.extend(map_calendar_item(event) for event in events)
    return sorted(result, key=lambda event: event.starts_at)[:30]


@internal_router.post("/invitations/respond")
async def bot_invitation_response(payload: BotInvitationReply, session: Session) -> dict[str, str]:
    user_id = await SqlPortalRepository(session).external_user(
        payload.provider.value, payload.external_user_id
    )
    if user_id is None:
        raise HTTPException(404, "Сначала пройдите регистрацию")
    try:
        invitation = await SqlEventLifecycleRepository(session).respond_to_invitation(
            payload.invitation_id, user_id, payload.accept
        )
    except LookupError as error:
        raise HTTPException(404, "Приглашение не найдено") from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    return {"status": invitation.status.value}


@router.get("/portal/ministries/{ministry_id}/roles")
async def ministry_roles(
    ministry_id: int, user_id: CurrentUser, session: Session
) -> list[dict[str, int | str]]:
    await require_portal_permission(session, user_id, ministry_id, "view_members")
    roles = await session.scalars(
        select(MinistryRoleRecord)
        .where(MinistryRoleRecord.church_ministry_id == ministry_id)
        .order_by(MinistryRoleRecord.name)
    )
    return [{"id": role.id, "name": role.name} for role in roles]


@router.post("/portal/ministries/{ministry_id}/members/{member_id}/roles", status_code=204)
async def add_member_role(
    ministry_id: int,
    member_id: int,
    payload: MemberRoleCreate,
    user_id: CurrentUser,
    session: Session,
) -> None:
    try:
        await MinistryService(
            SqlMinistryRepository(session), SqlChurchRepository(session)
        ).add_member_role(user_id, ministry_id, member_id, payload.ministry_role_id)
    except AccessDeniedError as error:
        raise HTTPException(403, str(error)) from error
    except (ParticipantNotFoundError, MinistryRoleNotFoundError) as error:
        raise HTTPException(404, "Участник или роль не найдены в этой команде") from error


@router.post("/portal/ministries/{ministry_id}/roles", status_code=201)
async def create_ministry_role(
    ministry_id: int, payload: MinistryRoleCreate, user_id: CurrentUser, session: Session
) -> dict[str, int | str]:
    await require_portal_permission(session, user_id, ministry_id, "manage_members")
    try:
        role = await MinistryService(
            SqlMinistryRepository(session), SqlChurchRepository(session)
        ).create_role(user_id, ministry_id, payload.name)
    except (ValueError, IntegrityError) as error:
        await session.rollback()
        raise HTTPException(409, "Роль с таким названием уже существует") from error
    return {"id": role.id, "name": role.name}


@router.post("/portal/events/{event_id}/role-slots", status_code=201)
async def add_event_participant(
    event_id: int, payload: PortalEventParticipant, user_id: CurrentUser, session: Session
) -> dict[str, int]:
    event = await session.scalar(
        select(EventRecord).where(EventRecord.id == event_id).with_for_update()
    )
    if event is None or event.church_ministry_id is None:
        raise HTTPException(404, "Событие не найдено")
    await require_portal_permission(
        session, user_id, event.church_ministry_id, "manage_assignments"
    )
    repository = SqlEventCalendarRepository(session)
    if not await repository.ministry_role_ids_belong_to(
        event.church_ministry_id, (payload.ministry_role_id,)
    ):
        raise HTTPException(422, "Выберите роль этого служения")
    if payload.user_ministry_role_id is not None:
        if not await repository.user_ministry_role_matches(
            payload.user_ministry_role_id, payload.ministry_role_id
        ):
            raise HTTPException(422, "Участник не имеет выбранной роли")
        if not await repository.user_role_ids_belong_to(
            event.church_ministry_id, (payload.user_ministry_role_id,)
        ):
            raise HTTPException(422, "Участник не состоит в этом служении")
        try:
            await require_role_eligible(session, payload.user_ministry_role_id, event.event_kind)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
    if payload.user_ministry_role_id is not None and await session.scalar(
        select(EventRoleSlotRecord.id)
        .where(
            EventRoleSlotRecord.event_id == event_id,
            EventRoleSlotRecord.user_ministry_role_id == payload.user_ministry_role_id,
        )
        .limit(1)
    ):
        raise HTTPException(409, "Этот служитель уже назначен на эту роль в событии")
    last = await session.scalar(
        select(func.max(EventRoleSlotRecord.slot_number)).where(
            EventRoleSlotRecord.event_id == event_id,
            EventRoleSlotRecord.ministry_role_id == payload.ministry_role_id,
        )
    )
    slot = EventRoleSlotRecord(
        event_id=event_id, ministry_role_id=payload.ministry_role_id, slot_number=(last or 0) + 1
    )
    session.add(slot)
    await session.flush()
    await assign_slot(
        slot.id,
        PortalAssignment(user_ministry_role_id=payload.user_ministry_role_id),
        user_id,
        session,
    )
    return {"id": slot.id}
