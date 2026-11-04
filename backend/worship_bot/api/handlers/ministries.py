from typing import Annotated

from fastapi import Depends, HTTPException, status

from worship_bot.api.dependencies import get_ministry_service, get_services
from worship_bot.api.schemas import (
    ChurchMinistryRead,
    MinistryAttachCreate,
    MinistryRoleCreate,
    MinistryRoleRead,
    MinistryTypeRead,
)
from worship_bot.api.security import get_current_user_id
from worship_bot.application.exceptions import (
    AccessDeniedError,
    ChurchMinistryNotFoundError,
    ChurchNotFoundError,
    MinistryRoleAlreadyExistsError,
)
from worship_bot.application.services import (
    ChurchService,
    MinistryService,
    ParticipantService,
    ScheduleService,
)

Ministries = Annotated[MinistryService, Depends(get_ministry_service)]
CurrentUserId = Annotated[int, Depends(get_current_user_id)]
Services = Annotated[
    tuple[ChurchService, ParticipantService, ScheduleService], Depends(get_services)
]


async def list_catalog(service: Ministries) -> list[MinistryTypeRead]:
    return [
        MinistryTypeRead(id=item.id, code=item.code, name=item.name)
        for item in await service.catalog()
    ]


async def list_church_ministries(church_id: int, service: Ministries) -> list[ChurchMinistryRead]:
    try:
        ministries = await service.church_ministries(church_id)
    except ChurchNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Church not found"
        ) from error
    return [
        ChurchMinistryRead(
            id=item.id,
            church_id=item.church_id,
            ministry_type_id=item.ministry_type_id,
            ministry_type_code=item.ministry_type_code,
            ministry_type_name=item.ministry_type_name,
        )
        for item in ministries
    ]


async def add_ministry_to_church(
    church_id: int,
    payload: MinistryAttachCreate,
    actor_user_id: CurrentUserId,
    service: Ministries,
) -> ChurchMinistryRead:
    try:
        item = await service.add_ministry_to_church(
            actor_user_id, church_id, payload.ministry_type_id
        )
    except ChurchNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Church not found"
        ) from error
    except AccessDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ministry type not found"
        ) from error
    return ChurchMinistryRead(
        id=item.id,
        church_id=item.church_id,
        ministry_type_id=item.ministry_type_id,
        ministry_type_code=item.ministry_type_code,
        ministry_type_name=item.ministry_type_name,
    )


async def list_roles(church_ministry_id: int, service: Ministries) -> list[MinistryRoleRead]:
    try:
        roles = await service.roles(church_ministry_id)
    except ChurchMinistryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ministry not found"
        ) from error
    return [
        MinistryRoleRead(
            id=role.id,
            church_ministry_id=role.church_ministry_id,
            code=role.code,
            name=role.name,
        )
        for role in roles
    ]


async def create_role(
    church_ministry_id: int,
    payload: MinistryRoleCreate,
    actor_user_id: CurrentUserId,
    service: Ministries,
) -> MinistryRoleRead:
    try:
        role = await service.create_role(actor_user_id, church_ministry_id, payload.name)
    except ChurchMinistryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ministry not found"
        ) from error
    except MinistryRoleAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Role already exists"
        ) from error
    except AccessDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    return MinistryRoleRead(
        id=role.id,
        church_ministry_id=role.church_ministry_id,
        code=role.code,
        name=role.name,
    )


async def create_role_for_self(
    church_ministry_id: int,
    payload: MinistryRoleCreate,
    actor_user_id: CurrentUserId,
    service: Ministries,
) -> MinistryRoleRead:
    try:
        role = await service.create_role_for_self(actor_user_id, church_ministry_id, payload.name)
    except ChurchMinistryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ministry not found"
        ) from error
    except MinistryRoleAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Role already exists"
        ) from error
    except AccessDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    return MinistryRoleRead(
        id=role.id,
        church_ministry_id=role.church_ministry_id,
        code=role.code,
        name=role.name,
    )
