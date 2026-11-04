from typing import Annotated

from fastapi import Depends, HTTPException, status

from worship_bot.api.dependencies import get_services
from worship_bot.api.schemas import ParticipantCreate, ParticipantRead
from worship_bot.application.commands import NewParticipant
from worship_bot.application.exceptions import (
    ChurchNotFoundError,
    ConsentRequiredError,
    ParticipantNotFoundError,
)
from worship_bot.application.services import ChurchService, ParticipantService, ScheduleService

Services = Annotated[
    tuple[ChurchService, ParticipantService, ScheduleService], Depends(get_services)
]


async def register_participant(payload: ParticipantCreate, services: Services) -> ParticipantRead:
    participants = services[1]
    try:
        participant = await participants.register(
            NewParticipant(
                name=payload.name,
                surname=payload.surname,
                church_id=payload.church_id,
                birthday_date=payload.birthday_date,
                consent_approved=payload.consent_approved,
                worship_roles=tuple(payload.worship_roles),
            )
        )
    except ConsentRequiredError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except ChurchNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Church not found"
        ) from error
    return ParticipantRead(
        id=participant.id,
        name=participant.name,
        surname=participant.surname,
        church_id=participant.church_id,
        birthday_date=participant.birthday_date,
        consent_approved=participant.consent_approved,
        worship_roles=list(participant.worship_roles),
    )


async def get_participant(participant_id: int, services: Services) -> ParticipantRead:
    participants = services[1]
    try:
        participant = await participants.get(participant_id)
    except ParticipantNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found"
        ) from error
    return ParticipantRead(
        id=participant.id,
        name=participant.name,
        surname=participant.surname,
        church_id=participant.church_id,
        birthday_date=participant.birthday_date,
        consent_approved=participant.consent_approved,
        worship_roles=list(participant.worship_roles),
    )
