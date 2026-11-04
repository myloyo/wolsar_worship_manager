from worship_bot.application.exceptions import (
    AccessDeniedError,
    ChurchMinistryNotFoundError,
    ChurchNotFoundError,
    MinistryRoleAlreadyExistsError,
    MinistryRoleNotFoundError,
    ParticipantNotFoundError,
)
from worship_bot.application.repositories import ChurchRepository, MinistryRepository
from worship_bot.domain.entities import ChurchMinistry, MinistryRoleDefinition, MinistryType


class MinistryService:
    manager_access_levels = {"coordinator", "admin", "developer"}

    def __init__(
        self,
        repository: MinistryRepository,
        church_repository: ChurchRepository,
    ) -> None:
        self.repository = repository
        self.church_repository = church_repository

    async def catalog(self) -> list[MinistryType]:
        return await self.repository.list_catalog()

    async def church_ministries(self, church_id: int) -> list[ChurchMinistry]:
        if not await self.church_repository.exists(church_id):
            raise ChurchNotFoundError(church_id)
        return await self.repository.list_church_ministries(church_id)

    async def roles(self, church_ministry_id: int) -> list[MinistryRoleDefinition]:
        if await self.repository.get_church_ministry(church_ministry_id) is None:
            raise ChurchMinistryNotFoundError(church_ministry_id)
        return await self.repository.list_roles(church_ministry_id)

    async def add_ministry_to_church(
        self,
        actor_user_id: int,
        church_id: int,
        ministry_type_id: int,
    ) -> ChurchMinistry:
        if not await self.church_repository.exists(church_id):
            raise ChurchNotFoundError(church_id)
        access_level = await self.repository.church_access_level(actor_user_id, church_id)
        if access_level not in {"admin", "developer"}:
            raise AccessDeniedError("Only church administrators can add a ministry")
        return await self.repository.add_to_church(church_id, ministry_type_id)

    async def create_role(
        self,
        actor_user_id: int,
        church_ministry_id: int,
        name: str,
    ) -> MinistryRoleDefinition:
        access_level = await self.repository.access_level(actor_user_id, church_ministry_id)
        if access_level not in self.manager_access_levels:
            raise AccessDeniedError(
                "Only ministry coordinators and administrators can manage roles"
            )
        return await self.create_validated_role(church_ministry_id, name, actor_user_id)

    async def create_role_for_self(
        self,
        actor_user_id: int,
        church_ministry_id: int,
        name: str,
    ) -> MinistryRoleDefinition:
        if await self.repository.access_level(actor_user_id, church_ministry_id) is None:
            raise AccessDeniedError("User is not a member of this ministry")
        role = await self.create_validated_role(church_ministry_id, name, actor_user_id)
        await self.repository.add_user_role(actor_user_id, church_ministry_id, role.id)
        return role

    async def add_member_role(
        self, actor_user_id: int, church_ministry_id: int, member_user_id: int, role_id: int
    ) -> None:
        actor_level = await self.repository.access_level(actor_user_id, church_ministry_id)
        if actor_level not in self.manager_access_levels:
            raise AccessDeniedError("Только координатор или администратор может назначать роли")
        if await self.repository.access_level(member_user_id, church_ministry_id) is None:
            raise ParticipantNotFoundError(member_user_id)
        roles = await self.repository.list_roles(church_ministry_id)
        if not any(role.id == role_id for role in roles):
            raise MinistryRoleNotFoundError(role_id)
        await self.repository.add_user_role(member_user_id, church_ministry_id, role_id)

    async def set_member_access_level(
        self,
        actor_user_id: int,
        church_ministry_id: int,
        member_user_id: int,
        access_level: str,
    ) -> None:
        actor_level = await self.repository.access_level(actor_user_id, church_ministry_id)
        if actor_level not in {"admin", "developer"}:
            raise AccessDeniedError("Only administrators can change ministry access")
        if access_level not in {"member", "coordinator", "admin"}:
            raise ValueError("Unsupported ministry access level")
        updated = await self.repository.set_access_level(
            member_user_id, church_ministry_id, access_level
        )
        if not updated:
            raise ParticipantNotFoundError(member_user_id)

    async def create_validated_role(
        self,
        church_ministry_id: int,
        name: str,
        actor_user_id: int,
    ) -> MinistryRoleDefinition:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Role name cannot be empty")
        if await self.repository.get_church_ministry(church_ministry_id) is None:
            raise ChurchMinistryNotFoundError(church_ministry_id)
        if await self.repository.get_role_by_name(church_ministry_id, normalized_name) is not None:
            raise MinistryRoleAlreadyExistsError(normalized_name)
        return await self.repository.create_role(church_ministry_id, normalized_name, actor_user_id)
