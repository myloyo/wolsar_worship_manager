import os
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from worship_bot.api.dependencies import get_event_calendar_service, get_services
from worship_bot.api.security import require_bot_service
from worship_bot.application.commands import (
    AssignEventRoleSlot,
    EventRoleSlotRequest,
    NewAssignment,
    NewChurch,
    NewEvent,
    NewEventRoleSlot,
    NewEventSeries,
    NewParticipant,
    StartRegistration,
)
from worship_bot.application.repositories import (
    ChurchRepository,
    EventCalendarRepository,
    IdentityRepository,
    MinistryRepository,
    ParticipantRepository,
    ScheduleRepository,
)
from worship_bot.application.services import (
    ChurchService,
    EventCalendarService,
    ParticipantService,
    RegistrationService,
    ScheduleService,
)
from worship_bot.domain.entities import (
    Church,
    ChurchMinistry,
    Event,
    EventAssignment,
    EventCalendarItem,
    EventRoleSlot,
    EventType,
    Participant,
    RegistrationDraft,
)
from worship_bot.domain.enums import (
    ConfirmationStatus,
    IdentityProvider,
    RegistrationStep,
    WorshipRole,
)
from worship_bot.main import app


@pytest.fixture
def participant_repository() -> AsyncMock:
    participants: dict[int, Participant] = {}

    async def create(participant: NewParticipant) -> Participant:
        result = Participant(
            id=len(participants) + 1,
            name=participant.name,
            surname=participant.surname,
            church_id=participant.church_id,
            birthday_date=participant.birthday_date,
            consent_approved=participant.consent_approved,
            worship_roles=participant.worship_roles,
        )
        participants[result.id] = result
        return result

    async def get_by_id(participant_id: int) -> Participant | None:
        return participants.get(participant_id)

    repository = AsyncMock(spec=ParticipantRepository)
    repository.create.side_effect = create
    repository.get_by_id.side_effect = get_by_id
    return repository


@pytest.fixture
def schedule_repository() -> AsyncMock:
    types = {1: EventType(1, "sunday_service", None, True)}
    events: dict[int, Event] = {}
    assignments: list[EventAssignment] = []

    async def get_event_type(event_type_id: int) -> EventType | None:
        return types.get(event_type_id)

    async def list_event_types() -> list[EventType]:
        return list(types.values())

    async def create_event(event: NewEvent) -> Event:
        result = Event(
            len(events) + 1,
            event.event_name,
            event.event_date,
            event.event_type_id,
            event.church_id,
        )
        events[result.id] = result
        return result

    async def list_events(start: datetime | None, end: datetime | None) -> list[Event]:
        return [
            event
            for event in events.values()
            if (start is None or event.event_date >= start)
            and (end is None or event.event_date <= end)
        ]

    async def participant_exists(participant_id: int) -> bool:
        return participant_id == 1

    async def event_exists(event_id: int) -> bool:
        return event_id in events

    async def add_assignment(
        assignment: NewAssignment, status: ConfirmationStatus
    ) -> EventAssignment:
        result = EventAssignment(
            len(assignments) + 1,
            assignment.event_id,
            assignment.user_id,
            assignment.worship_role,
            status,
        )
        assignments.append(result)
        return result

    repository = AsyncMock(spec=ScheduleRepository)
    repository.get_event_type.side_effect = get_event_type
    repository.list_event_types.side_effect = list_event_types
    repository.create_event.side_effect = create_event
    repository.list_events.side_effect = list_events
    repository.participant_exists.side_effect = participant_exists
    repository.event_exists.side_effect = event_exists
    repository.add_assignment.side_effect = add_assignment
    return repository


@pytest.fixture
def church_repository() -> AsyncMock:
    churches = {1: Church(1, "Церковь")}

    async def exists(church_id: int) -> bool:
        return church_id in churches

    async def get_by_name(name: str) -> Church | None:
        return next((church for church in churches.values() if church.name == name), None)

    async def create(church: NewChurch) -> Church:
        result = Church(len(churches) + 1, church.name)
        churches[result.id] = result
        return result

    async def list_all() -> list[Church]:
        return list(churches.values())

    repository = AsyncMock(spec=ChurchRepository)
    repository.exists.side_effect = exists
    repository.get_by_name.side_effect = get_by_name
    repository.create.side_effect = create
    repository.list_all.side_effect = list_all
    return repository


@pytest.fixture
def calendar_repository() -> AsyncMock:
    ministries = {1: ChurchMinistry(1, 1, 1, "worship"), 2: ChurchMinistry(2, 1, 2, "youth")}
    roles = {1: (1, "drums"), 2: (1, "bass"), 3: (2, "leader")}
    user_roles = {10: (1, 1), 20: (1, 2), 30: (2, 3)}
    available_song_ids = {501, 502}
    events: dict[int, EventCalendarItem] = {}
    next_event_id = 1
    next_series_id = 1
    next_slot_id = 1

    async def get_church_ministry(church_ministry_id: int) -> ChurchMinistry | None:
        return ministries.get(church_ministry_id)

    async def ministry_role_ids_belong_to(
        church_ministry_id: int, role_ids: tuple[int, ...]
    ) -> bool:
        return all(roles.get(role_id, (None, ""))[0] == church_ministry_id for role_id in role_ids)

    async def user_role_ids_belong_to(
        church_ministry_id: int, user_role_ids: tuple[int, ...]
    ) -> bool:
        for user_role_id in user_role_ids:
            user_role = user_roles.get(user_role_id)
            if user_role is None:
                return False
            role = roles.get(user_role[1])
            if role is None or role[0] != church_ministry_id:
                return False
        return True

    async def user_ministry_role_matches(user_ministry_role_id: int, ministry_role_id: int) -> bool:
        return user_roles.get(user_ministry_role_id, (None, None))[1] == ministry_role_id

    async def song_ids_exist(song_ids: tuple[int, ...]) -> bool:
        return all(song_id in available_song_ids for song_id in song_ids)

    async def create_event_series(
        series: NewEventSeries, occurrence_dates: tuple[datetime, ...]
    ) -> list[EventCalendarItem]:
        nonlocal next_event_id, next_series_id, next_slot_id
        church_ministry = ministries[series.church_ministry_id]
        series_id = next_series_id
        next_series_id += 1
        created: list[EventCalendarItem] = []
        for occurrence_date in occurrence_dates:
            event = Event(
                id=next_event_id,
                event_name=series.event_name,
                event_date=occurrence_date,
                event_type_id=None,
                church_id=church_ministry.church_id,
                church_ministry_id=church_ministry.id,
                event_series_id=series_id,
                additional_info=series.additional_info,
            )
            role_slots = tuple(
                (
                    EventRoleSlot(
                        id=next_slot_id + index,
                        event_id=event.id,
                        ministry_role_id=slot.ministry_role_id,
                        slot_number=slot.slot_number,
                        user_ministry_role_id=slot.user_ministry_role_id,
                        confirmation_status=ConfirmationStatus.PENDING,
                    )
                    for index, slot in enumerate(series.role_slots)
                )
            )
            next_slot_id += len(role_slots)
            item = EventCalendarItem(event, role_slots, series.song_ids)
            events[event.id] = item
            next_event_id += 1
            created.append(item)
        return created

    async def list_calendar_events(
        start: datetime, end: datetime, church_ministry_id: int | None
    ) -> list[EventCalendarItem]:
        return [
            item
            for item in events.values()
            if start <= item.event.event_date <= end
            and (church_ministry_id is None or item.event.church_ministry_id == church_ministry_id)
        ]

    async def get_event_ministry_id(event_id: int) -> int | None:
        item = events.get(event_id)
        return item.event.church_ministry_id if item is not None else None

    async def get_event_role_slot_ministry_id(slot_id: int) -> int | None:
        context = await get_event_role_slot_context(slot_id)
        return context[0] if context is not None else None

    async def get_event_role_slot_context(slot_id: int) -> tuple[int, int] | None:
        for item in events.values():
            for slot in item.role_slots:
                if slot.id == slot_id and item.event.church_ministry_id is not None:
                    return (item.event.church_ministry_id, slot.ministry_role_id)
        return None

    async def add_role_slot(slot: NewEventRoleSlot) -> EventRoleSlot:
        nonlocal next_slot_id
        item = events[slot.event_id]
        result = EventRoleSlot(
            next_slot_id,
            slot.event_id,
            slot.ministry_role_id,
            slot.slot_number,
            slot.user_ministry_role_id,
            ConfirmationStatus.PENDING,
        )
        next_slot_id += 1
        item.role_slots = (*item.role_slots, result)
        return result

    async def assign_role_slot(assignment: AssignEventRoleSlot) -> EventRoleSlot:
        for item in events.values():
            for slot in item.role_slots:
                if slot.id == assignment.event_role_slot_id:
                    slot.user_ministry_role_id = assignment.user_ministry_role_id
                    return slot
        raise LookupError(assignment.event_role_slot_id)

    repository = AsyncMock(spec=EventCalendarRepository)
    repository.default_role_slots.return_value = ()
    repository.get_church_ministry.side_effect = get_church_ministry
    repository.ministry_role_ids_belong_to.side_effect = ministry_role_ids_belong_to
    repository.user_role_ids_belong_to.side_effect = user_role_ids_belong_to
    repository.user_ministry_role_matches.side_effect = user_ministry_role_matches
    repository.song_ids_exist.side_effect = song_ids_exist
    repository.create_event_series.side_effect = create_event_series
    repository.list_calendar_events.side_effect = list_calendar_events
    repository.get_event_ministry_id.side_effect = get_event_ministry_id
    repository.get_event_role_slot_ministry_id.side_effect = get_event_role_slot_ministry_id
    repository.get_event_role_slot_context.side_effect = get_event_role_slot_context
    repository.add_role_slot.side_effect = add_role_slot
    repository.assign_role_slot.side_effect = assign_role_slot
    return repository


@pytest_asyncio.fixture
async def postgres_session() -> AsyncIterator[AsyncSession]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured; use `make test` for PostgreSQL tests")

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            yield session
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def api_client(
    church_service: ChurchService,
    participant_service: ParticipantService,
    schedule_service: ScheduleService,
    calendar_service: EventCalendarService,
) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[require_bot_service] = lambda: None
    previous_service_override = app.dependency_overrides.get(get_services)
    previous_calendar_override = app.dependency_overrides.get(get_event_calendar_service)
    app.dependency_overrides[get_services] = lambda: (
        church_service,
        participant_service,
        schedule_service,
    )
    app.dependency_overrides[get_event_calendar_service] = lambda: calendar_service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.pop(require_bot_service, None)
        if previous_service_override is None:
            app.dependency_overrides.pop(get_services, None)
        else:
            app.dependency_overrides[get_services] = previous_service_override
        if previous_calendar_override is None:
            app.dependency_overrides.pop(get_event_calendar_service, None)
        else:
            app.dependency_overrides[get_event_calendar_service] = previous_calendar_override


@pytest.fixture
def participant_service(
    participant_repository: AsyncMock, church_repository: AsyncMock
) -> ParticipantService:
    return ParticipantService(participant_repository, church_repository)


@pytest.fixture
def schedule_service(
    schedule_repository: AsyncMock, church_repository: AsyncMock
) -> ScheduleService:
    return ScheduleService(schedule_repository, church_repository)


@pytest.fixture
def church_service(church_repository: AsyncMock) -> ChurchService:
    return ChurchService(church_repository)


@pytest.fixture
def calendar_service(
    calendar_repository: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> EventCalendarService:
    clock = Mock(wraps=datetime)
    clock.now.return_value = datetime(2026, 10, 1, tzinfo=UTC)
    monkeypatch.setattr("worship_bot.application.services.events.datetime", clock)
    return EventCalendarService(calendar_repository)


@pytest.fixture
def sample_participant() -> NewParticipant:
    return NewParticipant(
        name="Анна",
        surname="Иванова",
        church_id=1,
        birthday_date=date(1995, 5, 20),
        consent_approved=True,
        worship_roles=(WorshipRole.BACK_VOCAL,),
    )


@pytest.fixture
def sample_event() -> NewEvent:
    return NewEvent(
        event_name="Воскресное собрание",
        event_date=datetime(2026, 10, 4, 10, tzinfo=UTC),
        event_type_id=1,
        church_id=1,
    )


@pytest.fixture
def sample_event_series() -> NewEventSeries:
    return NewEventSeries(
        church_ministry_id=1,
        event_name="Воскресное прославление",
        starts_at=datetime(2026, 11, 1, 10, tzinfo=UTC),
        timezone="Europe/Saratov",
        recurrence_rule="FREQ=WEEKLY;COUNT=3",
        repeats_until=None,
        additional_info="Репетиция за час до начала",
        song_ids=(501,),
        role_slots=(EventRoleSlotRequest(1, 1, 10),),
    )


@pytest.fixture
def registration_repositories() -> tuple[AsyncMock, AsyncMock, AsyncMock]:
    return (
        AsyncMock(spec=IdentityRepository),
        AsyncMock(spec=MinistryRepository),
        AsyncMock(spec=ChurchRepository),
    )


@pytest.fixture
def registration_service(
    registration_repositories: tuple[AsyncMock, AsyncMock, AsyncMock],
) -> RegistrationService:
    identity_repository, ministry_repository, church_repository = registration_repositories
    return RegistrationService(
        identity_repository,
        ministry_repository,
        church_repository,
        consent_version="test-policy-1",
    )


@pytest.fixture
def registration_identity() -> StartRegistration:
    return StartRegistration(
        provider=IdentityProvider.TELEGRAM,
        external_user_id="telegram-12345",
        external_username="anna_test",
    )


@pytest.fixture
def registration_draft() -> RegistrationDraft:
    return RegistrationDraft(
        id=12,
        provider=IdentityProvider.TELEGRAM,
        external_user_id="telegram-12345",
        external_username="anna_test",
        current_step=RegistrationStep.CHURCH,
        status="pending",
        registration_data={},
    )
