from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from worship_bot.api.assignment_schemas import (
    AssignmentResponse,
    BotAssignmentResponse,
    MyAssignment,
)
from worship_bot.api.routers.portal import CurrentUser, Session
from worship_bot.api.security import require_bot_service
from worship_bot.domain.notifications import assignment_revision
from worship_bot.infrastructure.models import (
    ChurchMinistryRecord,
    ChurchRecord,
    EventRecord,
    EventRoleSlotRecord,
    MinistryMembershipRecord,
    MinistryRoleRecord,
    MinistryTypeRecord,
    UserMinistryRoleRecord,
)
from worship_bot.infrastructure.repositories.assignments import respond_to_assignment
from worship_bot.infrastructure.repositories.portal import SqlPortalRepository

router = APIRouter(prefix="/portal/me/assignments", tags=["my events"])
internal_router = APIRouter(
    prefix="/internal/bot/assignments",
    tags=["bot assignments"],
    dependencies=[Depends(require_bot_service)],
)


@router.get("", response_model=list[MyAssignment])
async def my_events(user_id: CurrentUser, session: Session) -> list[MyAssignment]:
    rows = await session.execute(
        select(
            EventRoleSlotRecord,
            EventRecord,
            MinistryRoleRecord.name,
            MinistryTypeRecord.name,
            ChurchRecord.name,
        )
        .join(EventRecord, EventRecord.id == EventRoleSlotRecord.event_id)
        .join(
            UserMinistryRoleRecord,
            UserMinistryRoleRecord.id == EventRoleSlotRecord.user_ministry_role_id,
        )
        .join(
            MinistryMembershipRecord,
            MinistryMembershipRecord.id == UserMinistryRoleRecord.ministry_membership_id,
        )
        .join(MinistryRoleRecord, MinistryRoleRecord.id == EventRoleSlotRecord.ministry_role_id)
        .join(ChurchMinistryRecord, ChurchMinistryRecord.id == EventRecord.church_ministry_id)
        .join(MinistryTypeRecord, MinistryTypeRecord.id == ChurchMinistryRecord.ministry_type_id)
        .join(ChurchRecord, ChurchRecord.id == ChurchMinistryRecord.church_id)
        .where(
            MinistryMembershipRecord.user_id == user_id, EventRecord.event_date >= datetime.now(UTC)
        )
        .order_by(EventRecord.event_date, EventRoleSlotRecord.id)
    )
    return [
        MyAssignment(
            slot_id=slot.id,
            event_id=event.id,
            event_name=event.event_name,
            songs_text=event.songs_text,
            clothing_text=event.clothing_text,
            church_name=church,
            ministry_name=ministry,
            role_name=role,
            starts_at=event.event_date,
            rehearsal_at=event.rehearsal_at,
            additional_info=event.additional_info,
            status=slot.confirmation_status,
            revision=assignment_revision(slot.updated_at),
        )
        for slot, event, role, ministry, church in rows
    ]


@router.put("/{slot_id}", status_code=204)
async def respond(
    slot_id: int, payload: AssignmentResponse, user_id: CurrentUser, session: Session
) -> None:
    try:
        await respond_to_assignment(session, user_id, slot_id, payload.revision, payload.accept)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@internal_router.post("/respond", status_code=204)
async def bot_respond(payload: BotAssignmentResponse, session: Session) -> None:
    user_id = await SqlPortalRepository(session).external_user(
        payload.provider.value, payload.external_user_id
    )
    if user_id is None:
        raise HTTPException(404, "Привяжите Telegram в личной карточке на сайте")
    await respond(
        payload.slot_id,
        AssignmentResponse(accept=payload.accept, revision=payload.revision),
        user_id,
        session,
    )
