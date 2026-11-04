from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from worship_bot.application.commands import EventRoleSlotRequest, NewChurch, NewEventSeries
from worship_bot.application.services import EventCalendarService
from worship_bot.infrastructure.models import (
    ChurchMinistryRecord,
    ChurchRecord,
    EventSeriesRecord,
    MinistryRoleRecord,
    MinistryTypeRecord,
    SongRecord,
)
from worship_bot.infrastructure.repositories.churches import SqlChurchRepository
from worship_bot.infrastructure.repositories.events import SqlEventCalendarRepository


async def test_church_repository_persists_church(postgres_session: AsyncSession) -> None:
    # Arrange
    repository = SqlChurchRepository(postgres_session)
    church_name = f"integration-{uuid4()}"

    # Act
    church = await repository.create(NewChurch(church_name))
    try:
        exists = await repository.exists(church.id)
        persisted_church = await repository.get_by_name(church_name)

        # Assert
        assert exists
        assert persisted_church is not None
        assert persisted_church.id == church.id
    finally:
        await postgres_session.execute(delete(ChurchRecord).where(ChurchRecord.id == church.id))
        await postgres_session.commit()


async def test_event_series_persists_calendar_songs_and_roles(
    postgres_session: AsyncSession,
) -> None:
    # Arrange
    church_ministry_id = await postgres_session.scalar(
        select(ChurchMinistryRecord.id)
        .join(MinistryTypeRecord, MinistryTypeRecord.id == ChurchMinistryRecord.ministry_type_id)
        .where(MinistryTypeRecord.code == "worship")
        .limit(1)
    )
    assert church_ministry_id is not None
    role_id = await postgres_session.scalar(
        select(MinistryRoleRecord.id).where(
            MinistryRoleRecord.church_ministry_id == church_ministry_id,
            MinistryRoleRecord.code == "drums",
        )
    )
    assert role_id is not None
    song = SongRecord(song_name=f"integration-{uuid4()}")
    postgres_session.add(song)
    await postgres_session.commit()

    service = EventCalendarService(SqlEventCalendarRepository(postgres_session))
    series_id: int | None = None
    try:
        # Act
        events = await service.create_series(
            NewEventSeries(
                church_ministry_id=church_ministry_id,
                event_name="Integration series",
                starts_at=(datetime.now(UTC) + timedelta(days=1)).replace(microsecond=0),
                timezone="Europe/Saratov",
                recurrence_rule="FREQ=WEEKLY;COUNT=2",
                repeats_until=None,
                additional_info="Integration test note",
                song_ids=(song.id,),
                role_slots=(EventRoleSlotRequest(role_id, slot_number=1),),
            )
        )
        series_id = events[0].event.event_series_id

        # Assert
        assert len(events) == 2
        assert [event.song_ids for event in events] == [(song.id,), (song.id,)]
        assert all(len(event.role_slots) == 9 for event in events)
        assert all(event.event.additional_info == "Integration test note" for event in events)
    finally:
        if series_id is not None:
            await postgres_session.execute(
                delete(EventSeriesRecord).where(EventSeriesRecord.id == series_id)
            )
        await postgres_session.execute(delete(SongRecord).where(SongRecord.id == song.id))
        await postgres_session.commit()
