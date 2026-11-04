import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from worship_bot.api.event_preference_schemas import (
    EventContentUpdate,
    EventKindUpdate,
    EventNotificationUpdate,
    RoleEventKinds,
)
from worship_bot.api.handlers.events import map_calendar_item
from worship_bot.api.routers.portal import CurrentUser, Session, require_portal_permission
from worship_bot.api.schemas import EventCalendarItemRead
from worship_bot.application.exceptions import AccessDeniedError
from worship_bot.infrastructure.event_notifications import event_recipients
from worship_bot.infrastructure.models import EventNotificationPreferenceRecord, EventRecord
from worship_bot.infrastructure.notification_queue import queue_event_reminders
from worship_bot.infrastructure.repositories.event_preferences import SqlEventPreferencesRepository
from worship_bot.infrastructure.repositories.events import SqlEventCalendarRepository

router = APIRouter(tags=["event preferences"])
logger = logging.getLogger(__name__)


async def accessible_event(
    event_id: int, user_id: int, session: Session, permission: str = "view_schedule"
) -> EventRecord:
    event = await session.scalar(
        select(EventRecord).where(EventRecord.id == event_id).with_for_update()
    )
    if event is None or event.church_ministry_id is None:
        raise HTTPException(404, "Событие не найдено")
    await require_portal_permission(session, user_id, event.church_ministry_id, permission)
    return event


@router.get("/portal/events/{event_id}", response_model=EventCalendarItemRead)
async def event_details(
    event_id: int, user_id: CurrentUser, session: Session
) -> EventCalendarItemRead:
    await accessible_event(event_id, user_id, session)
    items = await SqlEventCalendarRepository(session).load_calendar_items((event_id,))
    return map_calendar_item(items[0])


@router.delete("/portal/events/{event_id}", status_code=204)
async def delete_event(event_id: int, user_id: CurrentUser, session: Session) -> None:
    event = await accessible_event(event_id, user_id, session, "manage_events")
    await session.delete(event)
    await session.commit()
    logger.info(
        "event.deleted",
        extra={"event_id": event_id, "user_id": user_id, "ministry_id": event.church_ministry_id},
    )


@router.get("/portal/events/{event_id}/notifications")
async def notification_preference(
    event_id: int, user_id: CurrentUser, session: Session
) -> dict[str, bool]:
    await accessible_event(event_id, user_id, session)
    return {"enabled": user_id in await event_recipients(session, event_id)}


@router.put("/portal/events/{event_id}/notifications", status_code=204)
async def set_notification_preference(
    event_id: int, payload: EventNotificationUpdate, user_id: CurrentUser, session: Session
) -> None:
    await accessible_event(event_id, user_id, session)
    preference = await session.get(EventNotificationPreferenceRecord, (event_id, user_id))
    if preference is None:
        session.add(
            EventNotificationPreferenceRecord(
                event_id=event_id, user_id=user_id, enabled=payload.enabled
            )
        )
    else:
        preference.enabled = payload.enabled
    await session.flush()
    await queue_event_reminders(session, event_id)
    await session.commit()
    logger.info(
        "event.notification_preference_changed",
        extra={
            "event_id": event_id,
            "user_id": user_id,
            "outcome": "enabled" if payload.enabled else "disabled",
        },
    )


def preference_error(error: Exception) -> HTTPException:
    return HTTPException(
        403
        if isinstance(error, AccessDeniedError)
        else 404
        if isinstance(error, LookupError)
        else 422,
        str(error),
    )


@router.put(
    "/portal/ministries/{ministry_id}/members/{member_id}/roles/{role_id}/event-kinds",
    status_code=204,
)
async def set_role_kinds(
    ministry_id: int,
    member_id: int,
    role_id: int,
    payload: RoleEventKinds,
    user_id: CurrentUser,
    session: Session,
) -> None:
    try:
        await SqlEventPreferencesRepository(session).set_role_kinds(
            user_id, ministry_id, member_id, role_id, list(payload.allowed_event_kinds)
        )
    except (AccessDeniedError, LookupError, ValueError) as error:
        raise preference_error(error) from error


@router.get("/portal/events/{event_id}/content-permission")
async def content_permission(
    event_id: int, user_id: CurrentUser, session: Session
) -> dict[str, bool]:
    event = await session.get(EventRecord, event_id)
    if event is None or event.church_ministry_id is None:
        raise HTTPException(404, "Событие не найдено")
    await require_portal_permission(session, user_id, event.church_ministry_id, "view_schedule")
    return {
        "can_edit": await SqlEventPreferencesRepository(session).can_edit_content(event_id, user_id)
    }


@router.put("/portal/events/{event_id}/content", status_code=204)
async def save_content(
    event_id: int, payload: EventContentUpdate, user_id: CurrentUser, session: Session
) -> None:
    try:
        await SqlEventPreferencesRepository(session).save_content(
            event_id, user_id, payload.revision, payload.songs_text, payload.clothing_text
        )
    except (AccessDeniedError, LookupError, ValueError) as error:
        raise preference_error(error) from error


@router.put("/portal/events/{event_id}/kind", status_code=204)
async def set_event_kind(
    event_id: int, payload: EventKindUpdate, user_id: CurrentUser, session: Session
) -> None:
    try:
        await SqlEventPreferencesRepository(session).set_event_kind(
            event_id, user_id, payload.event_kind
        )
    except (AccessDeniedError, LookupError, ValueError) as error:
        raise preference_error(error) from error
