import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select, update

from worship_bot.api.routers.portal import Session
from worship_bot.api.schemas import NotificationRead, NotificationResult
from worship_bot.api.security import require_bot_service
from worship_bot.domain.notifications import assignment_revision, format_service_datetime
from worship_bot.infrastructure.event_notifications import (
    event_notification_enabled,
    notification_allowed_clause,
)
from worship_bot.infrastructure.models import (
    EventRecord,
    EventRoleSlotRecord,
    EventSeriesRecord,
    ExternalAccountRecord,
    MinistryMembershipRecord,
    MinistryRoleRecord,
    NotificationJobRecord,
    UserMinistryRoleRecord,
)

router = APIRouter(
    prefix="/internal/notifications",
    tags=["notification delivery"],
    dependencies=[Depends(require_bot_service)],
)


@router.post("/claim", response_model=list[NotificationRead])
async def claim_notifications(session: Session) -> list[NotificationRead]:
    now = datetime.now(UTC)
    await session.execute(
        update(NotificationJobRecord)
        .where(
            NotificationJobRecord.status == "processing",
            NotificationJobRecord.attempts >= 5,
            NotificationJobRecord.locked_until < now,
        )
        .values(status="failed", claim_token=None, locked_until=None)
    )
    rows = await session.execute(
        select(NotificationJobRecord, ExternalAccountRecord.external_user_id)
        .join(ExternalAccountRecord, ExternalAccountRecord.user_id == NotificationJobRecord.user_id)
        .where(
            ExternalAccountRecord.provider == "telegram",
            notification_allowed_clause(),
            NotificationJobRecord.attempts < 5,
            NotificationJobRecord.scheduled_at <= now,
            or_(
                NotificationJobRecord.status == "pending",
                and_(
                    NotificationJobRecord.status == "processing",
                    NotificationJobRecord.locked_until < now,
                ),
            ),
        )
        .order_by(NotificationJobRecord.scheduled_at)
        .limit(20)
        .with_for_update(skip_locked=True, of=NotificationJobRecord)
    )
    result = []
    for job, external_user_id in rows:
        if not await event_notification_enabled(session, job):
            continue
        job.claim_token = secrets.token_urlsafe(24)
        job.status = "processing"
        job.locked_until = now + timedelta(minutes=5)
        job.attempts += 1
        event = await session.get(EventRecord, job.event_id)
        name = event.event_name if event is not None else "Служение"
        series = (
            await session.get(EventSeriesRecord, event.event_series_id)
            if event and event.event_series_id
            else None
        )
        timezone = series.timezone if series else "Europe/Saratov"
        starts_at = (
            event.rehearsal_at
            if event and job.notification_type.startswith("rehearsal")
            else event.event_date
            if event
            else None
        )
        if starts_at is None and isinstance(job.payload.get("starts_at"), str):
            try:
                starts_at = datetime.fromisoformat(str(job.payload["starts_at"]))
            except ValueError:
                pass
        labels = {
            "assignment": "Вы назначены на служение",
            "removed": "Вас сняли со служения",
            "invitation": "Вас пригласили на служение",
            "replacement": str(job.payload.get("text", "Replacement requested")),
            "event_content": "Обновлены песни или одежда. Откройте событие на сайте",
        }
        label = labels.get(
            job.notification_type,
            "Напоминание о репетиции"
            if job.notification_type.startswith("rehearsal")
            else "Напоминание о служении",
        )
        text = (
            str(job.payload.get("text", label))
            if job.notification_type == "replacement"
            else f"{label}\n{name}"
        )
        if starts_at and job.notification_type != "replacement":
            text += "\n" + format_service_datetime(starts_at, timezone) + " (местное время)"
        if job.notification_type == "invitation":
            text += "\nПодтвердите участие или откажитесь кнопкой ниже."
        slot = None
        if job.notification_type == "assignment":
            candidates = list(
                await session.scalars(
                    select(EventRoleSlotRecord)
                    .join(
                        UserMinistryRoleRecord,
                        UserMinistryRoleRecord.id == EventRoleSlotRecord.user_ministry_role_id,
                    )
                    .join(
                        MinistryMembershipRecord,
                        MinistryMembershipRecord.id
                        == UserMinistryRoleRecord.ministry_membership_id,
                    )
                    .where(
                        EventRoleSlotRecord.event_id == job.event_id,
                        MinistryMembershipRecord.user_id == job.user_id,
                    )
                )
            )
            slot_id = job.payload.get("slot_id")
            slot = (
                next((item for item in candidates if item.id == slot_id), None)
                if slot_id
                else candidates[0]
                if len(candidates) == 1
                else None
            )
            if slot_id and (
                slot is None
                or slot.user_ministry_role_id != job.payload.get("user_ministry_role_id")
            ):
                job.status, job.claim_token, job.locked_until = "cancelled", None, None
                continue
            if slot:
                role = await session.get(MinistryRoleRecord, slot.ministry_role_id)
                if role:
                    text += "\nВаша роль: " + role.name
            if slot and slot.confirmation_status != "pending":
                slot = None
        invitation_id = job.payload.get("invitation_id")
        result.append(
            NotificationRead(
                assignment_slot_id=slot.id if slot else None,
                assignment_revision=assignment_revision(slot.updated_at) if slot else None,
                id=job.id,
                claim_token=job.claim_token,
                external_user_id=external_user_id,
                text=text,
                invitation_id=invitation_id
                if job.notification_type == "invitation" and isinstance(invitation_id, int)
                else None,
            )
        )
    await session.commit()
    return result


@router.post("/{job_id}/result", status_code=204)
async def notification_result(job_id: int, payload: NotificationResult, session: Session) -> None:
    job = await session.scalar(
        select(NotificationJobRecord)
        .where(
            NotificationJobRecord.id == job_id,
            NotificationJobRecord.claim_token == payload.claim_token,
            NotificationJobRecord.status == "processing",
        )
        .with_for_update()
    )
    if job is None:
        raise HTTPException(409, "Задание уже обработано или выдано другому обработчику")
    job.status = "sent" if payload.delivered else "failed" if job.attempts >= 5 else "pending"
    if not payload.delivered:
        job.scheduled_at = datetime.now(UTC) + timedelta(seconds=min(3600, 30 * 2**job.attempts))
        job.last_error = "Delivery failed"
    job.claim_token = None
    job.locked_until = None
    await session.commit()
