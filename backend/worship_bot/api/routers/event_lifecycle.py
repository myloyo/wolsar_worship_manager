from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from worship_bot.api.dependencies import get_event_lifecycle_service
from worship_bot.api.schemas import (
    EventRoleSlotRead,
    InvitationCreate,
    InvitationRead,
    InvitationResponse,
    RoleSelection,
    ScheduleRead,
    ScheduleReplace,
    SongsReplace,
    SongVersionRead,
)
from worship_bot.api.security import get_current_user_id
from worship_bot.application.commands import (
    EditEventSongs,
    EventInvitationRequest,
    SetEventSchedule,
)
from worship_bot.application.exceptions import (
    AccessDeniedError,
    EventInvitationNotFoundError,
    EventInvitationStateError,
    EventNotFoundError,
    EventRoleSlotNotFoundError,
    EventSeriesValidationError,
    EventSongsNotAllowedError,
    UserMinistryRoleNotFoundError,
)
from worship_bot.application.services.events import EventLifecycleService

router = APIRouter(tags=["event participation"])
Service = Annotated[EventLifecycleService, Depends(get_event_lifecycle_service)]
User = Annotated[int, Depends(get_current_user_id)]


def api_error(error: Exception) -> HTTPException:
    if isinstance(error, AccessDeniedError):
        return HTTPException(403, str(error))
    if isinstance(
        error,
        (
            EventNotFoundError,
            EventInvitationNotFoundError,
            EventRoleSlotNotFoundError,
            UserMinistryRoleNotFoundError,
        ),
    ):
        return HTTPException(404, str(error))
    if isinstance(error, EventInvitationStateError):
        return HTTPException(409, str(error))
    if isinstance(error, (EventSeriesValidationError, EventSongsNotAllowedError)):
        return HTTPException(422, str(error))
    raise error


@router.put("/events/{event_id}/participation", response_model=EventRoleSlotRead)
async def signup(
    event_id: int, payload: RoleSelection, user: User, service: Service
) -> EventRoleSlotRead:
    try:
        slot = await service.self_signup(event_id, user, payload.ministry_role_id)
    except (AccessDeniedError, LookupError, ValueError) as error:
        raise api_error(error) from error
    return EventRoleSlotRead(**vars(slot))


@router.delete("/events/{event_id}/participation/{ministry_role_id}", status_code=204)
async def withdraw(event_id: int, ministry_role_id: int, user: User, service: Service) -> Response:
    try:
        await service.self_withdraw(event_id, user, ministry_role_id)
    except (AccessDeniedError, LookupError, ValueError) as error:
        raise api_error(error) from error
    return Response(status_code=204)


@router.post("/events/{event_id}/invitations", response_model=list[InvitationRead])
async def invite(
    event_id: int, payload: InvitationCreate, user: User, service: Service
) -> list[InvitationRead]:
    if any(value <= 0 for value in payload.user_ministry_role_ids):
        raise HTTPException(422, "Membership IDs must be positive")
    try:
        result = await service.invite(
            event_id,
            user,
            tuple(EventInvitationRequest(value) for value in payload.user_ministry_role_ids),
        )
    except (AccessDeniedError, LookupError, ValueError) as error:
        raise api_error(error) from error
    return [InvitationRead.model_validate(item) for item in result]


@router.get("/events/{event_id}/invitations", response_model=list[InvitationRead])
async def invitations(event_id: int, user: User, service: Service) -> list[InvitationRead]:
    try:
        result = await service.invitations(event_id, user)
    except (AccessDeniedError, LookupError, ValueError) as error:
        raise api_error(error) from error
    return [InvitationRead.model_validate(item) for item in result]


@router.put("/event-invitations/{invitation_id}/response", response_model=InvitationRead)
async def respond(
    invitation_id: int, payload: InvitationResponse, user: User, service: Service
) -> InvitationRead:
    try:
        result = await service.respond_to_invitation(invitation_id, user, payload.accept)
    except (AccessDeniedError, LookupError, ValueError) as error:
        raise api_error(error) from error
    return InvitationRead.model_validate(result)


@router.put("/events/{event_id}/schedule", response_model=ScheduleRead)
async def schedule(
    event_id: int, payload: ScheduleReplace, user: User, service: Service
) -> ScheduleRead:
    try:
        result = await service.set_schedule(
            SetEventSchedule(event_id, **payload.model_dump()), user
        )
    except (AccessDeniedError, LookupError, ValueError) as error:
        raise api_error(error) from error
    return ScheduleRead.model_validate(result)


@router.put("/events/{event_id}/songs", response_model=SongVersionRead)
async def songs(
    event_id: int, payload: SongsReplace, user: User, service: Service
) -> SongVersionRead:
    try:
        result = await service.edit_song_set(
            EditEventSongs(event_id, tuple(payload.song_ids), payload.comment), user
        )
    except (AccessDeniedError, LookupError, ValueError) as error:
        raise api_error(error) from error
    return SongVersionRead.model_validate(result)


@router.get("/events/{event_id}/songs/history", response_model=list[SongVersionRead])
async def song_history(event_id: int, user: User, service: Service) -> list[SongVersionRead]:
    try:
        result = await service.song_history(event_id, user)
    except (AccessDeniedError, LookupError, ValueError) as error:
        raise api_error(error) from error
    return [SongVersionRead.model_validate(item) for item in result]
