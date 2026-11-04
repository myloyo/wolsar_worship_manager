from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from worship_bot.api.dependencies import get_event_lifecycle_service
from worship_bot.api.security import get_current_user_id
from worship_bot.application.exceptions import AccessDeniedError, EventInvitationNotFoundError
from worship_bot.application.repositories import EventLifecycleRepository, MinistryRepository
from worship_bot.application.services.events import EventLifecycleService
from worship_bot.domain.entities import EventRoleSlot
from worship_bot.domain.enums import ConfirmationStatus
from worship_bot.main import app


@pytest.fixture
async def lifecycle_client() -> AsyncIterator[tuple[AsyncClient, AsyncMock]]:
    service = AsyncMock(spec=EventLifecycleService)
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user_id] = lambda: 7
    app.dependency_overrides[get_event_lifecycle_service] = lambda: service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, service
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


async def test_signup_uses_authenticated_identity(
    lifecycle_client: tuple[AsyncClient, AsyncMock],
) -> None:
    # Arrange
    client, service = lifecycle_client
    service.self_signup.return_value = EventRoleSlot(1, 10, 3, 1, 9, ConfirmationStatus.CONFIRMED)

    # Act
    response = await client.put("/api/v1/events/10/participation", json={"ministry_role_id": 3})

    # Assert
    assert response.status_code == 200
    assert response.json()["confirmation_status"] == "confirmed"
    service.self_signup.assert_awaited_once_with(10, 7, 3)


async def test_invite_forbidden_for_member(lifecycle_client: tuple[AsyncClient, AsyncMock]) -> None:
    # Arrange
    client, service = lifecycle_client
    service.invite.side_effect = AccessDeniedError("Manager required")

    # Act
    response = await client.post(
        "/api/v1/events/10/invitations", json={"user_ministry_role_ids": [9]}
    )

    # Assert
    assert response.status_code == 403


async def test_invitation_owned_by_another_user_is_hidden(
    lifecycle_client: tuple[AsyncClient, AsyncMock],
) -> None:
    # Arrange
    client, service = lifecycle_client
    service.respond_to_invitation.side_effect = EventInvitationNotFoundError(12)

    # Act
    response = await client.put("/api/v1/event-invitations/12/response", json={"accept": True})

    # Assert
    assert response.status_code == 404
    service.respond_to_invitation.assert_awaited_once_with(12, 7, True)


async def test_schedule_rejects_timezone_free_dates(
    lifecycle_client: tuple[AsyncClient, AsyncMock],
) -> None:
    # Arrange
    client, service = lifecycle_client

    # Act
    response = await client.put(
        "/api/v1/events/10/schedule", json={"rehearsal_at": "2026-11-01T10:00:00"}
    )

    # Assert
    assert response.status_code == 422
    service.set_schedule.assert_not_awaited()


async def test_withdraw_returns_empty_response(
    lifecycle_client: tuple[AsyncClient, AsyncMock],
) -> None:
    # Arrange
    client, service = lifecycle_client

    # Act
    response = await client.delete("/api/v1/events/10/participation/3")

    # Assert
    assert response.status_code == 204
    assert not response.content
    service.self_withdraw.assert_awaited_once_with(10, 7, 3)


async def test_song_history_requires_ministry_membership() -> None:
    # Arrange
    repository = AsyncMock(spec=EventLifecycleRepository)
    ministries = AsyncMock(spec=MinistryRepository)
    repository.get_event_context.return_value = (5, "worship")
    ministries.access_level.return_value = None
    service = EventLifecycleService(repository, ministries)

    # Act / Assert
    with pytest.raises(AccessDeniedError):
        await service.song_history(10, 7)

    # Assert
    repository.list_song_set_versions.assert_not_awaited()
