from typing import Annotated

from fastapi import Depends, HTTPException, status

from worship_bot.api.dependencies import get_services
from worship_bot.api.schemas import ChurchCreate, ChurchRead
from worship_bot.application.commands import NewChurch
from worship_bot.application.exceptions import ChurchAlreadyExistsError
from worship_bot.application.services import ChurchService, ParticipantService, ScheduleService

Services = Annotated[
    tuple[ChurchService, ParticipantService, ScheduleService], Depends(get_services)
]


async def create_church(payload: ChurchCreate, services: Services) -> ChurchRead:
    churches = services[0]
    try:
        church = await churches.create(NewChurch(payload.name))
    except ChurchAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Church already exists"
        ) from error
    return ChurchRead(id=church.id, name=church.name)


async def list_churches(services: Services) -> list[ChurchRead]:
    churches = services[0]
    return [ChurchRead(id=church.id, name=church.name) for church in await churches.list_all()]
