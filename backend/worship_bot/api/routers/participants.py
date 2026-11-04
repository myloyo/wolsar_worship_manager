from fastapi import APIRouter, Depends, status

from worship_bot.api.handlers import participants
from worship_bot.api.schemas import ParticipantRead
from worship_bot.api.security import require_bot_service

router = APIRouter(
    dependencies=[Depends(require_bot_service)], prefix="/participants", tags=["participants"]
)
router.add_api_route(
    "",
    participants.register_participant,
    methods=["POST"],
    response_model=ParticipantRead,
    status_code=status.HTTP_201_CREATED,
)
router.add_api_route(
    "/{participant_id}",
    participants.get_participant,
    methods=["GET"],
    response_model=ParticipantRead,
)
