from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worship_bot.application.services.planning import validate_proposal
from worship_bot.domain.planning import ScheduleProposal
from worship_bot.infrastructure.models import (
    ChurchMinistryRecord,
    EventRecord,
    EventRoleSlotRecord,
    NotificationJobRecord,
)
from worship_bot.infrastructure.models.portal import AssistantSessionRecord
from worship_bot.infrastructure.notification_queue import queue_event_reminders
from worship_bot.infrastructure.repositories.events import SqlEventCalendarRepository
from worship_bot.infrastructure.repositories.portal import SqlPortalRepository


class SqlPlanningRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def context(self, ministry_id: int, month: str) -> dict[str, Any]:
        start = datetime.strptime(month, "%Y-%m").replace(tzinfo=ZoneInfo("Europe/Saratov"))
        end = start + relativedelta(months=1)
        members = [
            asdict(member)
            for member in await SqlPortalRepository(self.session).members(ministry_id)
        ]
        calendar = await SqlEventCalendarRepository(self.session).list_calendar_events(
            start - relativedelta(months=2), end, ministry_id
        )
        events: list[dict[str, Any]] = []
        for item in calendar:
            starts_at = item.event.event_date
            if starts_at.tzinfo is None:
                starts_at = starts_at.replace(tzinfo=UTC)
            if starts_at >= end:
                continue
            events.append(
                {
                    "event_id": item.event.id,
                    "event_name": item.event.event_name,
                    "event_kind": item.event.event_kind,
                    "starts_at": starts_at.isoformat(),
                    "additional_info": item.event.additional_info,
                    "role_slots": [asdict(slot) for slot in item.role_slots],
                }
            )
        return {
            "month": month,
            "timezone": "Europe/Saratov",
            "members": members,
            "history": [
                event for event in events if datetime.fromisoformat(event["starts_at"]) < start
            ],
            "events": [
                event for event in events if datetime.fromisoformat(event["starts_at"]) >= start
            ],
        }

    async def create(self, user_id: int, ministry_id: int, month: str) -> AssistantSessionRecord:
        record = AssistantSessionRecord(
            id=str(uuid4()),
            user_id=user_id,
            church_ministry_id=ministry_id,
            month=month,
            messages=[],
            attachments=[],
            revision=0,
        )
        self.session.add(record)
        await self.session.commit()
        return record

    async def get(self, session_id: str, user_id: int) -> AssistantSessionRecord:
        record = await self.session.scalar(
            select(AssistantSessionRecord)
            .where(
                AssistantSessionRecord.id == session_id, AssistantSessionRecord.user_id == user_id
            )
            .with_for_update()
        )
        if record is None:
            raise LookupError("Диалог не найден")
        if record.applied_at is not None:
            raise ValueError("Черновик уже применён. Начните новый диалог")
        return record

    async def apply(self, record: AssistantSessionRecord, revision: int) -> list[int]:
        from worship_bot.domain.event_kinds import infer_event_kind
        from worship_bot.infrastructure.repositories.event_preferences import require_role_eligible

        if record.revision != revision or record.proposal is None:
            raise ValueError("Черновик изменился. Обновите его перед применением")
        ministry = await self.session.scalar(
            select(ChurchMinistryRecord)
            .where(ChurchMinistryRecord.id == record.church_ministry_id)
            .with_for_update()
        )
        if ministry is None:
            raise LookupError("Служение не найдено")
        context = await self.context(ministry.id, record.month)
        proposal = ScheduleProposal.model_validate(record.proposal)
        validate_proposal(proposal, record.month, context["members"], context["events"])
        if not proposal.events:
            raise ValueError("В черновике нет событий")
        role_users = {
            role["user_ministry_role_id"]: member["id"]
            for member in context["members"]
            for role in member["roles"]
        }
        ids = []
        event: EventRecord | None
        for planned in proposal.events:
            if planned.existing_event_id is None:
                if any(
                    datetime.fromisoformat(event["starts_at"]) == planned.starts_at
                    for event in context["events"]
                ):
                    raise ValueError("На это время уже существует событие. Пересоздайте черновик")
                event = EventRecord(
                    church_id=ministry.church_id,
                    church_ministry_id=ministry.id,
                    event_name=planned.event_name,
                    event_kind=infer_event_kind(planned.event_name),
                    event_date=planned.starts_at,
                    additional_info=planned.additional_info,
                )
                self.session.add(event)
                await self.session.flush()
                defaults = await SqlEventCalendarRepository(self.session).default_role_slots(
                    ministry.id
                )
                self.session.add_all(
                    EventRoleSlotRecord(
                        event_id=event.id,
                        ministry_role_id=slot.ministry_role_id,
                        slot_number=slot.slot_number,
                    )
                    for slot in defaults
                )
                await self.session.flush()
            else:
                event = await self.session.scalar(
                    select(EventRecord)
                    .where(EventRecord.id == planned.existing_event_id)
                    .with_for_update()
                )
                if event is None:
                    raise LookupError("Событие удалено")
            for assignment in planned.assignments:
                await require_role_eligible(
                    self.session, assignment.user_ministry_role_id, event.event_kind
                )
                slot = await self.session.scalar(
                    select(EventRoleSlotRecord)
                    .where(
                        EventRoleSlotRecord.event_id == event.id,
                        EventRoleSlotRecord.ministry_role_id == assignment.ministry_role_id,
                    )
                    .order_by(EventRoleSlotRecord.slot_number)
                )
                if slot is not None and slot.user_ministry_role_id not in (
                    None,
                    assignment.user_ministry_role_id,
                ):
                    raise ValueError("Роль уже занята. Черновик не применён")
                if slot is None:
                    slot = EventRoleSlotRecord(
                        event_id=event.id,
                        ministry_role_id=assignment.ministry_role_id,
                        slot_number=1,
                    )
                    self.session.add(slot)
                changed = slot.user_ministry_role_id != assignment.user_ministry_role_id
                slot.user_ministry_role_id = assignment.user_ministry_role_id
                if changed:
                    slot.confirmation_status = "pending"
                    key = f"assignment:{event.id}:{assignment.user_ministry_role_id}"
                    existing = await self.session.scalar(
                        select(NotificationJobRecord).where(
                            NotificationJobRecord.deduplication_key == key
                        )
                    )
                    if existing is None:
                        self.session.add(
                            NotificationJobRecord(
                                event_id=event.id,
                                user_id=role_users[assignment.user_ministry_role_id],
                                notification_type="assignment",
                                scheduled_at=datetime.now(UTC),
                                payload={
                                    "text": f"Вы назначены на {event.event_name}, "
                                    f"{event.event_date.isoformat()}"
                                },
                                deduplication_key=key,
                            )
                        )
            await self.session.flush()
            await queue_event_reminders(self.session, event.id)
            ids.append(event.id)
        record.applied_at = datetime.now(UTC)
        record.attachments = []
        await self.session.commit()
        return ids
