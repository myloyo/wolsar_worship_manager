from uuid import uuid4

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from worship_bot.api.routers.portal import CurrentUser, Session, require_portal_permission
from worship_bot.api.schemas import EventRoleSlotCreate
from worship_bot.api.template_schemas import (
    EventTemplateData,
    EventTemplateRead,
    default_event_templates,
)
from worship_bot.application.commands import EventRoleSlotRequest
from worship_bot.application.services import EventCalendarService
from worship_bot.infrastructure.models import ChurchMinistryRecord, EventTemplateRecord
from worship_bot.infrastructure.repositories.events import SqlEventCalendarRepository

router = APIRouter(prefix="/portal/ministries/{ministry_id}/templates", tags=["event templates"])


async def require_template_permission(
    session: Session, user_id: int, ministry_id: int, permission: str
) -> None:
    await require_portal_permission(session, user_id, ministry_id, permission)
    if await session.get(ChurchMinistryRecord, ministry_id) is None:
        raise HTTPException(404, "Служение не найдено")


async def validate_template(payload: EventTemplateData, ministry_id: int, session: Session) -> None:
    try:
        await EventCalendarService(SqlEventCalendarRepository(session)).validate_role_slots(
            ministry_id,
            tuple(
                EventRoleSlotRequest(
                    slot.ministry_role_id, slot.slot_number, slot.user_ministry_role_id
                )
                for slot in payload.role_slots
            ),
        )
    except (ValueError, LookupError) as error:
        raise HTTPException(422, str(error)) from error


@router.get("", response_model=list[EventTemplateRead])
async def list_templates(
    ministry_id: int, user_id: CurrentUser, session: Session
) -> list[EventTemplateRead]:
    await require_template_permission(session, user_id, ministry_id, "view_schedule")
    rows = await session.scalars(
        select(EventTemplateRecord)
        .where(EventTemplateRecord.church_ministry_id == ministry_id)
        .order_by(EventTemplateRecord.created_at)
    )
    templates = default_event_templates() + [
        EventTemplateRead.model_validate({"id": row.id, **row.details}) for row in rows
    ]
    service = EventCalendarService(SqlEventCalendarRepository(session))
    for template in templates:
        slots = await service.complete_role_slots(
            ministry_id,
            tuple(
                EventRoleSlotRequest(
                    slot.ministry_role_id, slot.slot_number, slot.user_ministry_role_id
                )
                for slot in template.role_slots
            ),
        )
        template.role_slots = [EventRoleSlotCreate(**vars(slot)) for slot in slots]
    return templates


@router.post("", response_model=EventTemplateRead, status_code=201)
async def create_template(
    ministry_id: int, payload: EventTemplateData, user_id: CurrentUser, session: Session
) -> EventTemplateRead:
    await require_template_permission(session, user_id, ministry_id, "manage_members")
    await validate_template(payload, ministry_id, session)
    record = EventTemplateRecord(
        id=str(uuid4()), church_ministry_id=ministry_id, details=payload.model_dump(mode="json")
    )
    session.add(record)
    await session.commit()
    return EventTemplateRead(id=record.id, **payload.model_dump())


@router.put("/{template_id}", response_model=EventTemplateRead)
async def update_template(
    ministry_id: int,
    template_id: str,
    payload: EventTemplateData,
    user_id: CurrentUser,
    session: Session,
) -> EventTemplateRead:
    await require_template_permission(session, user_id, ministry_id, "manage_members")
    record = await session.scalar(
        select(EventTemplateRecord).where(
            EventTemplateRecord.id == template_id,
            EventTemplateRecord.church_ministry_id == ministry_id,
        )
    )
    if record is None:
        raise HTTPException(404, "Шаблон не найден")
    await validate_template(payload, ministry_id, session)
    record.details = payload.model_dump(mode="json")
    await session.commit()
    return EventTemplateRead(id=record.id, **payload.model_dump())


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    ministry_id: int, template_id: str, user_id: CurrentUser, session: Session
) -> None:
    await require_template_permission(session, user_id, ministry_id, "manage_members")
    record = await session.scalar(
        select(EventTemplateRecord).where(
            EventTemplateRecord.id == template_id,
            EventTemplateRecord.church_ministry_id == ministry_id,
        )
    )
    if record is None:
        raise HTTPException(404, "Шаблон не найден")
    await session.delete(record)
    await session.commit()
