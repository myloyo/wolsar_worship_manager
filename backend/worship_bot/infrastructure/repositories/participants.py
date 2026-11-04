from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from worship_bot.application.commands import NewParticipant
from worship_bot.domain.entities import Participant
from worship_bot.domain.enums import WorshipRole
from worship_bot.infrastructure.models import UserRecord, UserWorshipAssignmentRecord


def map_participant(record: UserRecord) -> Participant:
    return Participant(
        id=record.id,
        name=record.name,
        surname=record.surname,
        church_id=record.church_id,
        birthday_date=record.birthday_date,
        consent_approved=record.consent_approved,
        worship_roles=tuple(WorshipRole(role.worship_role) for role in record.worship_roles),
    )


class SqlParticipantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, participant: NewParticipant) -> Participant:
        record = UserRecord(
            name=participant.name,
            surname=participant.surname,
            church_id=participant.church_id,
            birthday_date=participant.birthday_date,
            consent_approved=participant.consent_approved,
            worship_roles=[
                UserWorshipAssignmentRecord(worship_role=role.value)
                for role in participant.worship_roles
            ],
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record, attribute_names=["worship_roles"])
        return map_participant(record)

    async def get_by_id(self, participant_id: int) -> Participant | None:
        result = await self.session.execute(
            select(UserRecord)
            .options(selectinload(UserRecord.worship_roles))
            .where(UserRecord.id == participant_id)
        )
        record = result.scalar_one_or_none()
        return map_participant(record) if record is not None else None
