from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from hamcrest import assert_that, equal_to, has_length
from worship_bot.application.commands import (
    AssignEventRoleSlot,
    EventRoleSlotRequest,
    NewEventRoleSlot,
    NewEventSeries,
)
from worship_bot.application.exceptions import (
    EventSeriesValidationError,
    EventSongsNotAllowedError,
    InvalidRecurrenceRuleError,
    RoleAssignmentMismatchError,
)
from worship_bot.application.services import EventCalendarService


async def test_default_slots_preserve_assignments_and_extra_slots(
    calendar_service: EventCalendarService,
    calendar_repository: AsyncMock,
) -> None:
    # Arrange
    calendar_repository.default_role_slots.return_value = (
        EventRoleSlotRequest(1, 1),
        EventRoleSlotRequest(2, 1),
        EventRoleSlotRequest(2, 2),
    )
    explicit = (EventRoleSlotRequest(1, 1, 10), EventRoleSlotRequest(2, 3, 20))

    # Act
    slots = await calendar_service.complete_role_slots(1, explicit)

    # Assert
    assert slots[:2] == explicit
    assert slots[2] == EventRoleSlotRequest(2, 4)
    assert len(slots) == 3


async def test_default_slots_do_not_duplicate_full_lineup(
    calendar_service: EventCalendarService,
    calendar_repository: AsyncMock,
) -> None:
    # Arrange
    slots = (EventRoleSlotRequest(1, 1), EventRoleSlotRequest(2, 1), EventRoleSlotRequest(2, 2))
    calendar_repository.default_role_slots.return_value = slots

    # Act
    result = await calendar_service.complete_role_slots(1, slots)

    # Assert
    assert result == slots


@pytest.mark.parametrize("offset_seconds", [-86400, -1, 0])
async def test_create_series_rejects_started_events_without_writing(
    calendar_service: EventCalendarService,
    calendar_repository: AsyncMock,
    sample_event_series: NewEventSeries,
    offset_seconds: int,
) -> None:
    # Arrange: represent the same instant in the user's timezone.
    starts_at = (datetime(2026, 10, 1, tzinfo=UTC) + timedelta(seconds=offset_seconds)).astimezone(
        timezone(timedelta(hours=4))
    )
    request = replace(sample_event_series, starts_at=starts_at, recurrence_rule=None)

    # Act / Assert
    with pytest.raises(EventSeriesValidationError, match="должны быть в будущем"):
        await calendar_service.create_series(request)
    calendar_repository.create_event_series.assert_not_awaited()


async def test_create_series_accepts_later_today(
    calendar_service: EventCalendarService,
    calendar_repository: AsyncMock,
    sample_event_series: NewEventSeries,
) -> None:
    # Arrange
    request = replace(
        sample_event_series, starts_at=datetime(2026, 10, 1, 1, tzinfo=UTC), recurrence_rule=None
    )

    # Act
    await calendar_service.create_series(request)

    # Assert
    calendar_repository.create_event_series.assert_awaited_once()


async def test_create_series_materializes_calendar_dates(
    calendar_service: EventCalendarService,
    sample_event_series: NewEventSeries,
) -> None:
    # Act
    events = await calendar_service.create_series(sample_event_series)

    # Assert
    assert_that(events, has_length(3))
    assert_that(events[0].event.event_date.day, equal_to(1))
    assert_that(events[1].event.event_date.day, equal_to(8))
    assert_that(events[0].song_ids, equal_to((501,)))
    assert_that(events[0].role_slots[0].user_ministry_role_id, equal_to(10))


async def test_create_series_rejects_unbounded_recurrence(
    calendar_service: EventCalendarService,
    sample_event_series: NewEventSeries,
) -> None:
    # Arrange
    request = replace(sample_event_series, recurrence_rule="FREQ=WEEKLY")

    # Act / Assert
    with pytest.raises(InvalidRecurrenceRuleError, match="COUNT or UNTIL"):
        await calendar_service.create_series(request)


async def test_create_series_rejects_songs_for_non_worship_ministry(
    calendar_service: EventCalendarService,
    sample_event_series: NewEventSeries,
) -> None:
    # Arrange
    request = replace(sample_event_series, church_ministry_id=2, role_slots=())

    # Act / Assert
    with pytest.raises(EventSongsNotAllowedError):
        await calendar_service.create_series(request)


async def test_create_series_rejects_a_user_with_a_different_role(
    calendar_service: EventCalendarService,
    sample_event_series: NewEventSeries,
) -> None:
    # Arrange
    request = replace(
        sample_event_series,
        role_slots=(EventRoleSlotRequest(ministry_role_id=1, user_ministry_role_id=20),),
    )

    # Act / Assert
    with pytest.raises(RoleAssignmentMismatchError):
        await calendar_service.create_series(request)


async def test_role_slot_can_be_added_and_assigned(
    calendar_service: EventCalendarService,
    sample_event_series: NewEventSeries,
) -> None:
    # Arrange
    events = await calendar_service.create_series(sample_event_series)
    event = events[0].event
    slot = await calendar_service.add_role_slot(
        NewEventRoleSlot(event.id, ministry_role_id=2, slot_number=1)
    )

    # Act
    assignment = await calendar_service.assign_role_slot(AssignEventRoleSlot(slot.id, 20))

    # Assert
    assert_that(assignment.user_ministry_role_id, equal_to(20))
