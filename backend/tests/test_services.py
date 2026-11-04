from datetime import UTC, datetime

import pytest
from hamcrest import assert_that, equal_to, has_length
from worship_bot.application.commands import NewAssignment, NewChurch, NewEvent
from worship_bot.application.exceptions import (
    EventTypeNotFoundError,
    ParticipantNotFoundError,
)
from worship_bot.application.services import ChurchService, ParticipantService, ScheduleService
from worship_bot.domain.enums import ConfirmationStatus, WorshipRole


async def test_get_unknown_participant_raises_not_found(
    participant_service: ParticipantService,
) -> None:
    # Act / Assert
    with pytest.raises(ParticipantNotFoundError):
        await participant_service.get(404)


async def test_create_event_rejects_unknown_event_type(schedule_service: ScheduleService) -> None:
    # Arrange
    event = NewEvent("Семинар", datetime.now(UTC), event_type_id=404, church_id=1)

    # Act / Assert
    with pytest.raises(EventTypeNotFoundError):
        await schedule_service.create_event(event)


async def test_list_events_rejects_reversed_date_range(schedule_service: ScheduleService) -> None:
    # Arrange
    start = datetime(2026, 10, 10, tzinfo=UTC)
    end = datetime(2026, 10, 1, tzinfo=UTC)

    # Act / Assert
    with pytest.raises(ValueError, match="start must be earlier"):
        await schedule_service.events(start, end)


async def test_assignment_starts_pending(
    schedule_service: ScheduleService,
    sample_event: NewEvent,
) -> None:
    # Arrange
    event = await schedule_service.create_event(sample_event)

    # Act
    assignment = await schedule_service.assign(NewAssignment(event.id, 1, WorshipRole.DRUMS))

    # Assert
    assert_that(assignment.confirmation_status, equal_to(ConfirmationStatus.PENDING))
    assert_that(assignment.worship_role, equal_to(WorshipRole.DRUMS))


async def test_assignment_rejects_unknown_participant(
    schedule_service: ScheduleService,
    sample_event: NewEvent,
) -> None:
    # Act
    event = await schedule_service.create_event(sample_event)

    with pytest.raises(ParticipantNotFoundError):
        await schedule_service.assign(NewAssignment(event.id, 404, WorshipRole.DRUMS))


async def test_assignment_rejects_unknown_event(schedule_service: ScheduleService) -> None:
    # Act / Assert
    with pytest.raises(LookupError, match="404"):
        await schedule_service.assign(NewAssignment(404, 1, WorshipRole.DRUMS))


async def test_event_types_are_available(schedule_service: ScheduleService) -> None:
    # Act
    event_types = await schedule_service.event_types()

    # Assert
    assert_that(event_types, has_length(1))
    assert_that(event_types[0].code, equal_to("sunday_service"))


async def test_create_church_trims_name_and_lists_it(church_service: ChurchService) -> None:
    # Act
    church = await church_service.create(NewChurch("  Церковь Надежда  "))
    churches = await church_service.list_all()

    # Assert
    assert_that(church.name, equal_to("Церковь Надежда"))
    assert_that(churches, has_length(2))
