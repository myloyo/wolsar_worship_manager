from worship_bot.application.commands import NewChurch
from worship_bot.application.exceptions import ChurchAlreadyExistsError
from worship_bot.application.repositories import ChurchRepository
from worship_bot.domain.entities import Church


class ChurchService:
    def __init__(self, repository: ChurchRepository) -> None:
        self.repository = repository

    async def create(self, church: NewChurch) -> Church:
        name = church.name.strip()
        if not name:
            raise ValueError("Church name cannot be empty")
        if await self.repository.get_by_name(name) is not None:
            raise ChurchAlreadyExistsError(name)
        return await self.repository.create(NewChurch(name))

    async def list_all(self) -> list[Church]:
        return await self.repository.list_all()
