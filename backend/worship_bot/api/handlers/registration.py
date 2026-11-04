from typing import Annotated

from fastapi import Depends, HTTPException, status

from worship_bot.api.dependencies import get_registration_service
from worship_bot.api.schemas import (
    RegistrationCompleteRead,
    RegistrationDraftRead,
    RegistrationReviewRequest,
    RegistrationStart,
    RegistrationStepSubmit,
)
from worship_bot.api.security import create_access_token
from worship_bot.application.commands import AdvanceRegistration, StartRegistration
from worship_bot.application.exceptions import (
    ChurchNotFoundError,
    ConsentRequiredError,
    ExternalAccountAlreadyLinkedError,
    RegistrationDraftNotFoundError,
    RegistrationStepError,
)
from worship_bot.application.services import RegistrationService
from worship_bot.config import Settings, get_settings
from worship_bot.domain.entities import RegistrationDraft

Registration = Annotated[RegistrationService, Depends(get_registration_service)]


def map_registration_draft(draft: RegistrationDraft) -> RegistrationDraftRead:
    return RegistrationDraftRead(
        id=draft.id,
        current_step=draft.current_step,
        registration_data=draft.registration_data,
    )


async def start_registration(
    payload: RegistrationStart,
    service: Registration,
) -> RegistrationDraftRead:
    try:
        draft = await service.start(
            StartRegistration(
                provider=payload.provider,
                external_user_id=payload.external_user_id,
                external_username=payload.external_username,
            )
        )
    except ExternalAccountAlreadyLinkedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Account is already linked"
        ) from error
    return map_registration_draft(draft)


async def submit_registration_step(
    draft_id: int,
    payload: RegistrationStepSubmit,
    service: Registration,
) -> RegistrationDraftRead:
    try:
        draft = await service.advance(
            AdvanceRegistration(
                draft_id=draft_id,
                provider=payload.provider,
                external_user_id=payload.external_user_id,
                step=payload.step,
                answers=payload.answers,
            )
        )
    except RegistrationDraftNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found"
        ) from error
    except ChurchNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Church not found"
        ) from error
    except ConsentRequiredError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except RegistrationStepError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    return map_registration_draft(draft)


async def review_registration(
    draft_id: int,
    payload: RegistrationReviewRequest,
    service: Registration,
) -> RegistrationDraftRead:
    try:
        draft = await service.review(draft_id, payload.provider, payload.external_user_id)
    except RegistrationDraftNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found"
        ) from error
    except RegistrationStepError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return map_registration_draft(draft)


async def confirm_registration(
    draft_id: int,
    payload: RegistrationReviewRequest,
    service: Registration,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RegistrationCompleteRead:
    try:
        user_id = await service.confirm(draft_id, payload.provider, payload.external_user_id)
        token = create_access_token(user_id, settings)
    except RegistrationDraftNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found"
        ) from error
    except ConsentRequiredError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except RegistrationStepError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return RegistrationCompleteRead(user_id=user_id, access_token=token)
