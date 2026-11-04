from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from worship_bot.infrastructure.event_notifications import event_recipients
from worship_bot.infrastructure.models import (
    EventRecord,
    NotificationJobRecord,
)


async def queue_content_update(session: AsyncSession, event: EventRecord) -> None:
    event.content_revision += 1
    users = await event_recipients(session, event.id)
    for user_id in users:
        session.add(
            NotificationJobRecord(
                event_id=event.id,
                user_id=user_id,
                notification_type="event_content",
                scheduled_at=datetime.now(UTC),
                payload={
                    "text": f"Обновлены песни или одежда: {event.event_name}. "
                    "Откройте событие на сайте."
                },
                deduplication_key=f"content:{event.id}:{event.content_revision}:{user_id}",
            )
        )


async def queue_event_reminders(session: AsyncSession, event_id: int) -> None:
    event = await session.get(EventRecord, event_id)
    if event is None:
        return

    assigned_users = await event_recipients(session, event_id)
    await session.execute(
        update(NotificationJobRecord)
        .where(
            NotificationJobRecord.event_id == event_id,
            NotificationJobRecord.notification_type.in_(
                ("event", "rehearsal", "event_2h", "rehearsal_2h")
            ),
            NotificationJobRecord.status == "pending",
            NotificationJobRecord.user_id.not_in(assigned_users),
        )
        .values(status="cancelled")
    )
    reminder_types = (
        ("event", event.event_reminder_at, event.event_date),
        ("rehearsal", event.rehearsal_reminder_at, event.rehearsal_at),
        (
            "event_2h",
            event.event_date - timedelta(hours=2)
            if event.event_reminder_at is not None
            and event.event_reminder_at != event.event_date - timedelta(hours=2)
            else None,
            event.event_date,
        ),
        (
            "rehearsal_2h",
            event.rehearsal_at - timedelta(hours=2)
            if event.rehearsal_at is not None
            and event.rehearsal_reminder_at is not None
            and event.rehearsal_reminder_at != event.rehearsal_at - timedelta(hours=2)
            else None,
            event.rehearsal_at,
        ),
    )
    for user_id in assigned_users:
        for notification_type, scheduled_at, starts_at in reminder_types:
            if scheduled_at is None or starts_at is None:
                await session.execute(
                    update(NotificationJobRecord)
                    .where(
                        NotificationJobRecord.event_id == event_id,
                        NotificationJobRecord.user_id == user_id,
                        NotificationJobRecord.notification_type == notification_type,
                        NotificationJobRecord.status == "pending",
                    )
                    .values(status="cancelled")
                )
                continue
            deduplication_key = f"event:{event_id}:user:{user_id}:{notification_type}"
            job = await session.scalar(
                select(NotificationJobRecord).where(
                    NotificationJobRecord.deduplication_key == deduplication_key
                )
            )
            payload = {
                "event_name": event.event_name,
                "event_id": event.id,
                "starts_at": starts_at.isoformat(),
                "additional_info": event.additional_info,
            }
            if job is None:
                session.add(
                    NotificationJobRecord(
                        event_id=event_id,
                        user_id=user_id,
                        notification_type=notification_type,
                        scheduled_at=scheduled_at,
                        payload=payload,
                        deduplication_key=deduplication_key,
                    )
                )
            elif (
                job.scheduled_at != scheduled_at
                or job.payload != payload
                or job.status == "cancelled"
            ):
                job.scheduled_at = scheduled_at
                job.payload = payload
                job.status = "pending"
                job.attempts = 0
                job.last_error = None
    await session.flush()
