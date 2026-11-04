from worship_bot.application.commands import NewParticipant
from worship_bot.application.exceptions import (
    ChurchNotFoundError,
    ConsentRequiredError,
    ParticipantNotFoundError,
)
from worship_bot.application.repositories import ChurchRepository, ParticipantRepository
from worship_bot.domain.entities import Participant


class ParticipantService:
    def __init__(
        self,
        repository: ParticipantRepository,
        church_repository: ChurchRepository,
    ) -> None:
        self.repository = repository
        self.church_repository = church_repository

    async def register(self, participant: NewParticipant) -> Participant:
        if not participant.consent_approved:
            raise ConsentRequiredError("Data processing consent is required")
        if not await self.church_repository.exists(participant.church_id):
            raise ChurchNotFoundError(participant.church_id)
        return await self.repository.create(participant)

    async def get(self, participant_id: int) -> Participant:
        participant = await self.repository.get_by_id(participant_id)
        if participant is None:
            raise ParticipantNotFoundError(participant_id)
        return participant
