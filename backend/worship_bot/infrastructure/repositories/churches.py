from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worship_bot.application.commands import NewChurch
from worship_bot.domain.entities import Church
from worship_bot.infrastructure.models import ChurchRecord


class SqlChurchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def exists(self, church_id: int) -> bool:
        return await self.session.get(ChurchRecord, church_id) is not None

    async def get_by_name(self, name: str) -> Church | None:
        result = await self.session.scalar(select(ChurchRecord).where(ChurchRecord.name == name))
        return Church(result.id, result.name) if result is not None else None

    async def create(self, church: NewChurch) -> Church:
        record = ChurchRecord(name=church.name)
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return Church(record.id, record.name)

    async def list_all(self) -> list[Church]:
        records = await self.session.scalars(select(ChurchRecord).order_by(ChurchRecord.name))
        return [Church(record.id, record.name) for record in records]
