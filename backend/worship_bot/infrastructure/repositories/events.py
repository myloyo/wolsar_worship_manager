from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from worship_bot.application.commands import (
    AssignEventRoleSlot,
    EventRoleSlotRequest,
    NewAssignment,
    NewEvent,
    NewEventRoleSlot,
    NewEventSeries,
)
from worship_bot.domain.entities import (
    ChurchMinistry,
    Event,
    EventAssignment,
    EventCalendarItem,
    EventRoleSlot,
    EventType,
)
from worship_bot.domain.enums import ConfirmationStatus, WorshipRole
from worship_bot.domain.worship_roles import WORSHIP_EVENT_ROLE_COUNTS
from worship_bot.infrastructure.models import (
    ChurchMembershipRecord,
    ChurchMinistryRecord,
    EventParticipantRecord,
    EventRecord,
    EventRoleSlotRecord,
    EventSeriesRecord,
    EventSongRecord,
    EventTypeRecord,
    MinistryRoleRecord,
    MinistryTypeRecord,
    SongRecord,
    UserMinistryRoleRecord,
    UserRecord,
)
from worship_bot.infrastructure.notification_queue import queue_event_reminders


class SqlScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_event_type(self, event_type_id: int) -> EventType | None:
        record = await self.session.get(EventTypeRecord, event_type_id)
        if record is None:
            return None
        return EventType(record.id, record.code, record.custom_name, record.is_default)

    async def list_event_types(self) -> list[EventType]:
        records = await self.session.scalars(select(EventTypeRecord).order_by(EventTypeRecord.id))
        return [EventType(row.id, row.code, row.custom_name, row.is_default) for row in records]

    async def create_event(self, event: NewEvent) -> Event:
        record = EventRecord(
            event_name=event.event_name,
            event_date=event.event_date,
            event_type_id=event.event_type_id,
            church_id=event.church_id,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return Event(
            record.id, record.event_name, record.event_date, record.event_type_id, record.church_id
        )

    async def list_events(self, start: datetime | None, end: datetime | None) -> list[Event]:
        query = select(EventRecord).order_by(EventRecord.event_date)
        if start is not None:
            query = query.where(EventRecord.event_date >= start)
        if end is not None:
            query = query.where(EventRecord.event_date <= end)
        records = await self.session.scalars(query)
        return [
            Event(row.id, row.event_name, row.event_date, row.event_type_id, row.church_id)
            for row in records
        ]

    async def participant_exists(self, participant_id: int) -> bool:
        return await self.session.get(UserRecord, participant_id) is not None

    async def event_exists(self, event_id: int) -> bool:
        return await self.session.get(EventRecord, event_id) is not None

    async def add_assignment(
        self,
        assignment: NewAssignment,
        status: ConfirmationStatus,
    ) -> EventAssignment:
        record = EventParticipantRecord(
            event_id=assignment.event_id,
            user_id=assignment.user_id,
            worship_role=assignment.worship_role.value,
            confirmation_status=status.value,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return EventAssignment(
            record.id,
            record.event_id,
            record.user_id,
            WorshipRole(record.worship_role),
            ConfirmationStatus(record.confirmation_status),
        )


class SqlEventCalendarRepository:
    async def default_role_slots(self, church_ministry_id: int) -> tuple[EventRoleSlotRequest, ...]:
        ministry = await self.get_church_ministry(church_ministry_id)
        if ministry is None or ministry.ministry_type_code != "worship":
            return ()
        roles = await self.session.scalars(
            select(MinistryRoleRecord).where(
                MinistryRoleRecord.church_ministry_id == church_ministry_id
            )
        )
        by_code = {role.code: role.id for role in roles}
        return tuple(
            EventRoleSlotRequest(by_code[code], number)
            for code, count in WORSHIP_EVENT_ROLE_COUNTS
            if code in by_code
            for number in range(1, count + 1)
        )

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_church_ministry(self, church_ministry_id: int) -> ChurchMinistry | None:
        result = await self.session.execute(
            select(ChurchMinistryRecord, MinistryTypeRecord.code)
            .join(
                MinistryTypeRecord, MinistryTypeRecord.id == ChurchMinistryRecord.ministry_type_id
            )
            .where(ChurchMinistryRecord.id == church_ministry_id)
        )
        row = result.one_or_none()
        if row is None:
            return None
        ministry, ministry_code = row
        return ChurchMinistry(
            id=ministry.id,
            church_id=ministry.church_id,
            ministry_type_id=ministry.ministry_type_id,
            ministry_type_code=ministry_code,
        )

    async def ministry_role_ids_belong_to(
        self, church_ministry_id: int, role_ids: tuple[int, ...]
    ) -> bool:
        if not role_ids:
            return True
        count = await self.session.scalar(
            select(func.count(func.distinct(MinistryRoleRecord.id))).where(
                MinistryRoleRecord.church_ministry_id == church_ministry_id,
                MinistryRoleRecord.id.in_(role_ids),
            )
        )
        return count == len(set(role_ids))

    async def user_role_ids_belong_to(
        self, church_ministry_id: int, user_role_ids: tuple[int, ...]
    ) -> bool:
        if not user_role_ids:
            return True
        statement = (
            select(func.count(func.distinct(UserMinistryRoleRecord.id)))
            .join(
                MinistryRoleRecord, MinistryRoleRecord.id == UserMinistryRoleRecord.ministry_role_id
            )
            .join(
                ChurchMembershipRecord,
                ChurchMembershipRecord.id == UserMinistryRoleRecord.church_membership_id,
            )
            .join(
                ChurchMinistryRecord,
                (ChurchMinistryRecord.church_id == ChurchMembershipRecord.church_id)
                & (ChurchMinistryRecord.id == MinistryRoleRecord.church_ministry_id),
            )
            .where(
                ChurchMinistryRecord.id == church_ministry_id,
                UserMinistryRoleRecord.id.in_(user_role_ids),
            )
        )
        count = await self.session.scalar(statement)
        return count == len(set(user_role_ids))

    async def user_ministry_role_matches(
        self, user_ministry_role_id: int, ministry_role_id: int
    ) -> bool:
        return (
            await self.session.scalar(
                select(UserMinistryRoleRecord.id).where(
                    UserMinistryRoleRecord.id == user_ministry_role_id,
                    UserMinistryRoleRecord.ministry_role_id == ministry_role_id,
                )
            )
            is not None
        )

    async def song_ids_exist(self, song_ids: tuple[int, ...]) -> bool:
        if not song_ids:
            return True
        count = await self.session.scalar(
            select(func.count(func.distinct(SongRecord.id))).where(SongRecord.id.in_(song_ids))
        )
        return count == len(set(song_ids))

    async def create_event_series(
        self,
        series: NewEventSeries,
        occurrence_dates: tuple[datetime, ...],
    ) -> list[EventCalendarItem]:
        from worship_bot.domain.event_kinds import infer_event_kind
        from worship_bot.infrastructure.repositories.event_preferences import require_role_eligible

        kind = series.event_kind or infer_event_kind(series.event_name)
        for slot in series.role_slots:
            if slot.user_ministry_role_id is not None:
                await require_role_eligible(self.session, slot.user_ministry_role_id, kind)
        series_record = EventSeriesRecord(
            church_ministry_id=series.church_ministry_id,
            event_name=series.event_name,
            starts_at=series.starts_at,
            timezone=series.timezone,
            recurrence_rule=series.recurrence_rule,
            repeats_until=series.repeats_until,
            additional_info=series.additional_info,
        )
        self.session.add(series_record)
        await self.session.flush()
        ministry = await self.get_church_ministry(series.church_ministry_id)
        if ministry is None:
            raise LookupError(series.church_ministry_id)
        event_records = [
            EventRecord(
                event_name=series.event_name,
                event_date=event_date,
                event_type_id=None,
                church_id=ministry.church_id,
                church_ministry_id=series.church_ministry_id,
                event_series_id=series_record.id,
                rehearsal_at=(
                    event_date - timedelta(minutes=series.rehearsal_offset_minutes)
                    if series.rehearsal_offset_minutes is not None
                    else None
                ),
                event_reminder_at=event_date - timedelta(days=1)
                if series.reminders_enabled
                else None,
                rehearsal_reminder_at=(
                    event_date - timedelta(minutes=series.rehearsal_offset_minutes, days=1)
                    if series.reminders_enabled and series.rehearsal_offset_minutes is not None
                    else None
                ),
                additional_info=series.additional_info,
                event_kind=kind,
            )
            for event_date in occurrence_dates
        ]
        self.session.add_all(event_records)
        await self.session.flush()
        for event in event_records:
            self.session.add_all(
                [
                    EventSongRecord(song_id=song_id, event_id=event.id, position=position)
                    for position, song_id in enumerate(series.song_ids)
                ]
            )
            self.session.add_all(
                [
                    EventRoleSlotRecord(
                        event_id=event.id,
                        ministry_role_id=slot.ministry_role_id,
                        slot_number=slot.slot_number,
                        user_ministry_role_id=slot.user_ministry_role_id,
                        confirmation_status=ConfirmationStatus.PENDING.value,
                    )
                    for slot in series.role_slots
                ]
            )
        await self.session.flush()
        for event in event_records:
            await queue_event_reminders(self.session, event.id)
        await self.session.commit()
        return await self.load_calendar_items(tuple(event.id for event in event_records))

    async def list_calendar_events(
        self, start: datetime, end: datetime, church_ministry_id: int | None
    ) -> list[EventCalendarItem]:
        query = select(EventRecord).where(
            EventRecord.event_date >= start,
            EventRecord.event_date <= end,
        )
        if church_ministry_id is not None:
            query = query.where(EventRecord.church_ministry_id == church_ministry_id)
        records = await self.session.scalars(query.order_by(EventRecord.event_date))
        return await self.load_calendar_items(tuple(record.id for record in records))

    async def get_event_ministry_id(self, event_id: int) -> int | None:
        return await self.session.scalar(
            select(EventRecord.church_ministry_id).where(EventRecord.id == event_id)
        )

    async def get_event_role_slot_ministry_id(self, slot_id: int) -> int | None:
        context = await self.get_event_role_slot_context(slot_id)
        return context[0] if context is not None else None

    async def get_event_role_slot_context(self, slot_id: int) -> tuple[int, int] | None:
        result = await self.session.execute(
            select(EventRecord.church_ministry_id, EventRoleSlotRecord.ministry_role_id)
            .join(EventRoleSlotRecord, EventRoleSlotRecord.event_id == EventRecord.id)
            .where(EventRoleSlotRecord.id == slot_id)
        )
        row = result.one_or_none()
        if row is None or row.church_ministry_id is None:
            return None
        return row.church_ministry_id, row.ministry_role_id

    async def add_role_slot(self, slot: NewEventRoleSlot) -> EventRoleSlot:
        from worship_bot.infrastructure.repositories.event_preferences import require_role_eligible

        event = await self.session.get(EventRecord, slot.event_id)
        if event is not None and slot.user_ministry_role_id is not None:
            await require_role_eligible(self.session, slot.user_ministry_role_id, event.event_kind)
        record = EventRoleSlotRecord(
            event_id=slot.event_id,
            ministry_role_id=slot.ministry_role_id,
            slot_number=slot.slot_number,
            user_ministry_role_id=slot.user_ministry_role_id,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return self.map_role_slot(record)

    async def assign_role_slot(self, assignment: AssignEventRoleSlot) -> EventRoleSlot:
        from worship_bot.infrastructure.repositories.event_preferences import require_role_eligible

        target_event = await self.session.scalar(
            select(EventRecord)
            .join(EventRoleSlotRecord, EventRoleSlotRecord.event_id == EventRecord.id)
            .where(EventRoleSlotRecord.id == assignment.event_role_slot_id)
        )
        if target_event is not None:
            await require_role_eligible(
                self.session, assignment.user_ministry_role_id, target_event.event_kind
            )
        await self.session.execute(
            update(EventRoleSlotRecord)
            .where(EventRoleSlotRecord.id == assignment.event_role_slot_id)
            .values(
                user_ministry_role_id=assignment.user_ministry_role_id,
                confirmation_status=ConfirmationStatus.PENDING.value,
            )
        )
        await self.session.commit()
        record = await self.session.get(EventRoleSlotRecord, assignment.event_role_slot_id)
        if record is None:
            raise LookupError(assignment.event_role_slot_id)
        return self.map_role_slot(record)

    async def load_calendar_items(self, event_ids: tuple[int, ...]) -> list[EventCalendarItem]:
        if not event_ids:
            return []
        events = await self.session.scalars(
            select(EventRecord)
            .where(EventRecord.id.in_(event_ids))
            .order_by(EventRecord.event_date)
        )
        slots = await self.session.scalars(
            select(EventRoleSlotRecord)
            .where(EventRoleSlotRecord.event_id.in_(event_ids))
            .order_by(
                EventRoleSlotRecord.event_id,
                EventRoleSlotRecord.ministry_role_id,
                EventRoleSlotRecord.slot_number,
            )
        )
        songs = await self.session.scalars(
            select(EventSongRecord)
            .where(EventSongRecord.event_id.in_(event_ids))
            .order_by(EventSongRecord.event_id, EventSongRecord.position)
        )
        slots_by_event: dict[int, list[EventRoleSlot]] = defaultdict(list)
        songs_by_event: dict[int, list[int]] = defaultdict(list)
        for slot in slots:
            slots_by_event[slot.event_id].append(self.map_role_slot(slot))
        for song in songs:
            songs_by_event[song.event_id].append(song.song_id)
        return [
            EventCalendarItem(
                event=Event(
                    id=event.id,
                    event_name=event.event_name,
                    event_date=event.event_date,
                    event_type_id=event.event_type_id,
                    church_id=event.church_id,
                    church_ministry_id=event.church_ministry_id,
                    event_series_id=event.event_series_id,
                    additional_info=event.additional_info,
                    event_kind=event.event_kind,
                    songs_text=event.songs_text,
                    clothing_text=event.clothing_text,
                    content_revision=event.content_revision,
                    rehearsal_at=event.rehearsal_at,
                    event_reminder_at=event.event_reminder_at,
                    rehearsal_reminder_at=event.rehearsal_reminder_at,
                ),
                role_slots=tuple(slots_by_event[event.id]),
                song_ids=tuple(songs_by_event[event.id]),
            )
            for event in events
        ]

    @staticmethod
    def map_role_slot(record: EventRoleSlotRecord) -> EventRoleSlot:
        return EventRoleSlot(
            id=record.id,
            event_id=record.event_id,
            ministry_role_id=record.ministry_role_id,
            slot_number=record.slot_number,
            user_ministry_role_id=record.user_ministry_role_id,
            confirmation_status=ConfirmationStatus(record.confirmation_status),
        )
