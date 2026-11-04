from fastapi import APIRouter, Depends

from worship_bot.api.handlers import registration
from worship_bot.api.schemas import (
    RegistrationCompleteRead,
    RegistrationDraftRead,
)
from worship_bot.api.security import require_bot_service

router = APIRouter(
    prefix="/internal/registrations",
    tags=["registration"],
    dependencies=[Depends(require_bot_service)],
)
router.add_api_route(
    "",
    registration.start_registration,
    methods=["POST"],
    response_model=RegistrationDraftRead,
)
router.add_api_route(
    "/{draft_id}/steps",
    registration.submit_registration_step,
    methods=["POST"],
    response_model=RegistrationDraftRead,
)
router.add_api_route(
    "/{draft_id}/review",
    registration.review_registration,
    methods=["POST"],
    response_model=RegistrationDraftRead,
)
router.add_api_route(
    "/{draft_id}/confirm",
    registration.confirm_registration,
    methods=["POST"],
    response_model=RegistrationCompleteRead,
)
