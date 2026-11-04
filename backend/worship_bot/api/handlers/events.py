from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Query, status

from worship_bot.api.dependencies import get_event_calendar_service, get_services
from worship_bot.api.schemas import (
    AssignmentCreate,
    AssignmentRead,
    EventCalendarItemRead,
    EventCreate,
    EventRead,
    EventRoleSlotAssign,
    EventRoleSlotCreate,
    EventRoleSlotRead,
    EventSeriesCreate,
    EventTypeRead,
)
from worship_bot.application.commands import (
    AssignEventRoleSlot,
    EventRoleSlotRequest,
    NewAssignment,
    NewEvent,
    NewEventRoleSlot,
    NewEventSeries,
)
from worship_bot.application.exceptions import (
    ChurchMinistryNotFoundError,
    ChurchNotFoundError,
    EventNotFoundError,
    EventRoleSlotNotFoundError,
    EventSeriesValidationError,
    EventSongsNotAllowedError,
    EventTypeNotFoundError,
    InvalidRecurrenceRuleError,
    MinistryRoleNotFoundError,
    ParticipantNotFoundError,
    RoleAssignmentMismatchError,
    UserMinistryRoleNotFoundError,
)
from worship_bot.application.services import (
    ChurchService,
    EventCalendarService,
    ParticipantService,
    ScheduleService,
)
from worship_bot.domain.entities import EventCalendarItem, EventRoleSlot
from worship_bot.domain.enums import ConfirmationStatus

Services = Annotated[
    tuple[ChurchService, ParticipantService, ScheduleService], Depends(get_services)
]
CalendarService = Annotated[EventCalendarService, Depends(get_event_calendar_service)]


def map_event_role_slot(slot: EventRoleSlot) -> EventRoleSlotRead:
    return EventRoleSlotRead(
        id=slot.id,
        event_id=slot.event_id,
        ministry_role_id=slot.ministry_role_id,
        slot_number=slot.slot_number,
        user_ministry_role_id=slot.user_ministry_role_id,
        confirmation_status=slot.confirmation_status,
    )


def map_calendar_item(item: EventCalendarItem) -> EventCalendarItemRead:
    event = item.event
    if event.church_id is None or event.church_ministry_id is None:
        raise ValueError("Calendar event must be associated with a church ministry")
    return EventCalendarItemRead(
        event_id=event.id,
        event_name=event.event_name,
        starts_at=event.event_date,
        event_kind=event.event_kind,
        songs_text=event.songs_text,
        clothing_text=event.clothing_text,
        content_revision=event.content_revision,
        church_id=event.church_id,
        church_ministry_id=event.church_ministry_id,
        event_series_id=event.event_series_id,
        additional_info=event.additional_info,
        song_ids=list(item.song_ids),
        rehearsal_at=event.rehearsal_at,
        event_reminder_at=event.event_reminder_at,
        rehearsal_reminder_at=event.rehearsal_reminder_at,
        role_slots=[map_event_role_slot(slot) for slot in item.role_slots],
    )


async def list_event_types(services: Services) -> list[EventTypeRead]:
    schedule = services[2]
    return [
        EventTypeRead(
            id=event_type.id,
            code=event_type.code,
            custom_name=event_type.custom_name,
            is_default=event_type.is_default,
        )
        for event_type in await schedule.event_types()
    ]


async def create_event(payload: EventCreate, services: Services) -> EventRead:
    schedule = services[2]
    try:
        event = await schedule.create_event(
            NewEvent(
                payload.event_name,
                payload.event_date,
                payload.event_type_id,
                payload.church_id,
            )
        )
    except EventTypeNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event type not found"
        ) from error
    except ChurchNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Church not found"
        ) from error
    return EventRead(
        id=event.id,
        event_name=event.event_name,
        event_date=event.event_date,
        event_type_id=event.event_type_id,
        church_id=event.church_id,
    )


async def list_events(
    services: Services,
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
) -> list[EventRead]:
    schedule = services[2]
    try:
        events = await schedule.events(start, end)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    return [
        EventRead(
            id=event.id,
            event_name=event.event_name,
            event_date=event.event_date,
            event_type_id=event.event_type_id,
            church_id=event.church_id,
        )
        for event in events
    ]


async def assign_participant(
    event_id: int,
    payload: AssignmentCreate,
    services: Services,
) -> AssignmentRead:
    schedule = services[2]
    try:
        assignment = await schedule.assign(
            NewAssignment(event_id, payload.user_id, payload.worship_role),
            ConfirmationStatus.PENDING,
        )
    except ParticipantNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found"
        ) from error
    except EventNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        ) from error
    return AssignmentRead(
        id=assignment.id,
        event_id=assignment.event_id,
        user_id=assignment.user_id,
        worship_role=assignment.worship_role,
        confirmation_status=assignment.confirmation_status,
    )


async def create_event_series(
    church_ministry_id: int,
    payload: EventSeriesCreate,
    calendar: CalendarService,
) -> list[EventCalendarItemRead]:
    try:
        events = await calendar.create_series(
            NewEventSeries(
                church_ministry_id=church_ministry_id,
                event_name=payload.event_name,
                event_kind=payload.event_kind,
                rehearsal_offset_minutes=(
                    int((payload.starts_at - payload.rehearsal_at).total_seconds() / 60)
                    if payload.rehearsal_at is not None
                    else None
                ),
                reminders_enabled=payload.reminders_enabled,
                starts_at=payload.starts_at,
                timezone=payload.timezone,
                recurrence_rule=payload.recurrence_rule,
                repeats_until=payload.repeats_until,
                additional_info=payload.additional_info,
                song_ids=tuple(payload.song_ids),
                role_slots=tuple(
                    EventRoleSlotRequest(
                        ministry_role_id=slot.ministry_role_id,
                        slot_number=slot.slot_number,
                        user_ministry_role_id=slot.user_ministry_role_id,
                    )
                    for slot in payload.role_slots
                ),
            )
        )
    except ChurchMinistryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ministry not found"
        ) from error
    except (MinistryRoleNotFoundError, UserMinistryRoleNotFoundError) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (
        InvalidRecurrenceRuleError,
        EventSeriesValidationError,
        EventSongsNotAllowedError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    return [map_calendar_item(event) for event in events]


async def list_calendar_events(
    calendar: CalendarService,
    start: Annotated[datetime, Query()],
    end: Annotated[datetime, Query()],
    church_ministry_id: Annotated[int | None, Query(gt=0)] = None,
) -> list[EventCalendarItemRead]:
    try:
        events = await calendar.list_events(start, end, church_ministry_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    return [map_calendar_item(event) for event in events]


async def add_event_role_slot(
    event_id: int,
    payload: EventRoleSlotCreate,
    calendar: CalendarService,
) -> EventRoleSlotRead:
    try:
        slot = await calendar.add_role_slot(
            NewEventRoleSlot(
                event_id=event_id,
                ministry_role_id=payload.ministry_role_id,
                slot_number=payload.slot_number,
                user_ministry_role_id=payload.user_ministry_role_id,
            )
        )
    except (
        EventRoleSlotNotFoundError,
        MinistryRoleNotFoundError,
        UserMinistryRoleNotFoundError,
    ) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (RoleAssignmentMismatchError, EventSeriesValidationError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    return map_event_role_slot(slot)


async def assign_event_role_slot(
    slot_id: int,
    payload: EventRoleSlotAssign,
    calendar: CalendarService,
) -> EventRoleSlotRead:
    try:
        slot = await calendar.assign_role_slot(
            AssignEventRoleSlot(slot_id, payload.user_ministry_role_id)
        )
    except (EventRoleSlotNotFoundError, UserMinistryRoleNotFoundError) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (RoleAssignmentMismatchError, EventSeriesValidationError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    return map_event_role_slot(slot)
