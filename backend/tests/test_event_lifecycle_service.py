from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from worship_bot.application.commands import (
    EditEventSongs,
    EventInvitationRequest,
    SetEventSchedule,
)
from worship_bot.application.exceptions import AccessDeniedError, EventSeriesValidationError
from worship_bot.application.repositories import EventLifecycleRepository, MinistryRepository
from worship_bot.application.services.events import EventLifecycleService
from worship_bot.domain.entities import Event


@pytest.fixture
def lifecycle_repository() -> AsyncMock:
    repository = AsyncMock(spec=EventLifecycleRepository)
    repository.get_event_context.return_value = (5, "worship")
    return repository


@pytest.fixture
def lifecycle_ministries() -> AsyncMock:
    ministries = AsyncMock(spec=MinistryRepository)
    ministries.access_level.return_value = "member"
    return ministries


@pytest.fixture
def lifecycle_service(
    lifecycle_repository: AsyncMock, lifecycle_ministries: AsyncMock
) -> EventLifecycleService:
    return EventLifecycleService(lifecycle_repository, lifecycle_ministries)


async def test_member_cannot_invite(
    lifecycle_repository: AsyncMock, lifecycle_service: EventLifecycleService
) -> None:
    # Act / Assert
    with pytest.raises(AccessDeniedError):
        await lifecycle_service.invite(10, 7, (EventInvitationRequest(9),))

    # Assert
    lifecycle_repository.invite_candidates.assert_not_awaited()


async def test_duplicate_invite_candidates_are_rejected(
    lifecycle_repository: AsyncMock,
    lifecycle_ministries: AsyncMock,
    lifecycle_service: EventLifecycleService,
) -> None:
    # Arrange
    lifecycle_ministries.access_level.return_value = "coordinator"

    # Act / Assert
    with pytest.raises(EventSeriesValidationError):
        await lifecycle_service.invite(
            10, 7, (EventInvitationRequest(9), EventInvitationRequest(9))
        )

    # Assert
    lifecycle_repository.invite_candidates.assert_not_awaited()


async def test_rehearsal_cannot_follow_event(
    lifecycle_repository: AsyncMock,
    lifecycle_ministries: AsyncMock,
    lifecycle_service: EventLifecycleService,
) -> None:
    # Arrange
    lifecycle_ministries.access_level.return_value = "coordinator"
    lifecycle_repository.get_event.return_value = Event(
        10, "Service", datetime(2026, 11, 1, tzinfo=UTC), None, 1
    )

    # Act / Assert
    with pytest.raises(EventSeriesValidationError):
        await lifecycle_service.set_schedule(
            SetEventSchedule(10, datetime(2026, 11, 2, tzinfo=UTC), None, None), 7
        )

    # Assert
    lifecycle_repository.set_event_schedule.assert_not_awaited()


async def test_history_is_hidden_from_nonmembers(
    lifecycle_repository: AsyncMock,
    lifecycle_ministries: AsyncMock,
    lifecycle_service: EventLifecycleService,
) -> None:
    # Arrange
    lifecycle_ministries.access_level.return_value = None

    # Act / Assert
    with pytest.raises(AccessDeniedError):
        await lifecycle_service.song_history(10, 7)

    # Assert
    lifecycle_repository.list_song_set_versions.assert_not_awaited()


async def test_song_edit_requires_permission(
    lifecycle_repository: AsyncMock,
    lifecycle_ministries: AsyncMock,
    lifecycle_service: EventLifecycleService,
) -> None:
    # Arrange
    lifecycle_ministries.can_edit_song_set.return_value = False

    # Act / Assert
    with pytest.raises(AccessDeniedError):
        await lifecycle_service.edit_song_set(EditEventSongs(10, (1,)), 7)

    # Assert
    lifecycle_repository.replace_song_set.assert_not_awaited()


async def test_signup_uses_role_owned_by_authenticated_user(
    lifecycle_repository: AsyncMock, lifecycle_service: EventLifecycleService
) -> None:
    # Arrange
    lifecycle_repository.get_user_role_for_event.return_value = 9

    # Act
    await lifecycle_service.self_signup(10, 7, 3)

    # Assert
    lifecycle_repository.get_user_role_for_event.assert_awaited_once_with(10, 7, 3)
    lifecycle_repository.self_signup.assert_awaited_once_with(10, 7, 9)
