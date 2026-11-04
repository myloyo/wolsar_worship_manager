from unittest.mock import AsyncMock

import pytest
from worship_bot.application.exceptions import (
    AccessDeniedError,
    MinistryRoleNotFoundError,
    ParticipantNotFoundError,
)
from worship_bot.application.repositories import ChurchRepository, MinistryRepository
from worship_bot.application.services import MinistryService
from worship_bot.domain.entities import MinistryRoleDefinition


@pytest.mark.parametrize("access", ["coordinator", "admin", "developer"])
async def test_manager_can_add_role_to_self_without_changing_access(access: str) -> None:
    # Arrange
    repository = AsyncMock(spec=MinistryRepository)
    repository.access_level.return_value = access
    repository.list_roles.return_value = [
        MinistryRoleDefinition(
            id=4, church_ministry_id=1, code="sound", name="Звук", created_by_user_id=None
        )
    ]
    service = MinistryService(repository, AsyncMock(spec=ChurchRepository))

    # Act
    await service.add_member_role(7, 1, 7, 4)

    # Assert
    repository.add_user_role.assert_awaited_once_with(7, 1, 4)
    repository.set_access_level.assert_not_awaited()


@pytest.mark.parametrize("access", [None, "member"])
async def test_member_cannot_add_roles(access: str | None) -> None:
    # Arrange
    repository = AsyncMock(spec=MinistryRepository)
    repository.access_level.return_value = access
    service = MinistryService(repository, AsyncMock(spec=ChurchRepository))

    # Act / Assert
    with pytest.raises(AccessDeniedError):
        await service.add_member_role(7, 1, 8, 4)
    repository.add_user_role.assert_not_awaited()


async def test_cannot_add_role_to_nonmember() -> None:
    # Arrange
    repository = AsyncMock(spec=MinistryRepository)
    repository.access_level.side_effect = ["admin", None]
    service = MinistryService(repository, AsyncMock(spec=ChurchRepository))

    # Act / Assert
    with pytest.raises(ParticipantNotFoundError):
        await service.add_member_role(7, 1, 8, 4)
    repository.add_user_role.assert_not_awaited()


async def test_cannot_add_role_from_another_team() -> None:
    # Arrange
    repository = AsyncMock(spec=MinistryRepository)
    repository.access_level.side_effect = ["coordinator", "member"]
    repository.list_roles.return_value = []
    service = MinistryService(repository, AsyncMock(spec=ChurchRepository))

    # Act / Assert
    with pytest.raises(MinistryRoleNotFoundError):
        await service.add_member_role(7, 1, 8, 4)
    repository.add_user_role.assert_not_awaited()
