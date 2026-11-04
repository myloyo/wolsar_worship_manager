import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worship_bot.domain.notifications import assignment_revision, format_service_datetime
from worship_bot.infrastructure.models import (
    EventRecord,
    EventRoleSlotRecord,
    EventSeriesRecord,
    MinistryMembershipRecord,
    MinistryRoleRecord,
    NotificationJobRecord,
    UserMinistryRoleRecord,
    UserRecord,
)
from worship_bot.infrastructure.notification_queue import queue_event_reminders

logger = logging.getLogger(__name__)


async def respond_to_assignment(
    session: AsyncSession, user_id: int, slot_id: int, revision: str, accept: bool
) -> None:
    event_id = await session.scalar(
        select(EventRoleSlotRecord.event_id).where(EventRoleSlotRecord.id == slot_id)
    )
    if event_id is None:
        raise LookupError("Назначение больше не доступно")
    event = await session.scalar(
        select(EventRecord).where(EventRecord.id == event_id).with_for_update()
    )
    slot = await session.scalar(
        select(EventRoleSlotRecord)
        .join(
            UserMinistryRoleRecord,
            UserMinistryRoleRecord.id == EventRoleSlotRecord.user_ministry_role_id,
        )
        .join(
            MinistryMembershipRecord,
            MinistryMembershipRecord.id == UserMinistryRoleRecord.ministry_membership_id,
        )
        .where(
            EventRoleSlotRecord.id == slot_id,
            MinistryMembershipRecord.user_id == user_id,
            MinistryMembershipRecord.church_ministry_id == EventRecord.church_ministry_id,
        )
        .join(EventRecord, EventRecord.id == EventRoleSlotRecord.event_id)
        .with_for_update(of=EventRoleSlotRecord)
    )
    if slot is None or event is None:
        raise LookupError("Назначение больше не доступно")
    await session.refresh(slot)
    if not accept and slot.confirmation_status == "replacement":
        return
    if assignment_revision(slot.updated_at) != revision:
        raise ValueError("Назначение изменилось. Обновите «Доступность»")
    starts = event.event_date if event.event_date.tzinfo else event.event_date.replace(tzinfo=UTC)
    if starts < datetime.now(UTC):
        raise ValueError("Событие уже началось")
    slot.confirmation_status = "confirmed" if accept else "replacement"
    if not accept:
        series = (
            await session.get(EventSeriesRecord, event.event_series_id)
            if event.event_series_id
            else None
        )
        starts_text = format_service_datetime(
            event.event_date, series.timezone if series else "Europe/Saratov"
        )
        person = await session.get(UserRecord, user_id)
        role = await session.get(MinistryRoleRecord, slot.ministry_role_id)
        recipients = await session.scalars(
            select(MinistryMembershipRecord.user_id)
            .where(
                MinistryMembershipRecord.church_ministry_id == event.church_ministry_id,
                MinistryMembershipRecord.access_level.in_(("admin", "coordinator", "developer")),
                MinistryMembershipRecord.user_id != user_id,
            )
            .distinct()
        )
        await session.flush()
        for recipient in recipients:
            session.add(
                NotificationJobRecord(
                    event_id=event.id,
                    user_id=recipient,
                    notification_type="replacement",
                    scheduled_at=datetime.now(UTC),
                    payload={
                        "text": f"{person.name if person else ''} "
                        f"{person.surname if person else ''} "
                        f"просит замену: {event.event_name}, "
                        f"{role.name if role else 'роль'}, {starts_text}. "
                        "Откройте событие, чтобы назначить замену."
                    },
                    deduplication_key=f"replacement:{slot.id}:{assignment_revision(slot.updated_at)}:{recipient}",
                )
            )
    await session.flush()
    await queue_event_reminders(session, event.id)
    await session.commit()
    logger.info(
        "assignment.response_saved",
        extra={
            "event_id": event.id,
            "user_id": user_id,
            "slot_id": slot_id,
            "outcome": "confirmed" if accept else "replacement_requested",
        },
    )
