from fastapi import APIRouter, Depends, status

from worship_bot.api.handlers import churches
from worship_bot.api.schemas import ChurchRead
from worship_bot.api.security import require_bot_service

router = APIRouter(
    dependencies=[Depends(require_bot_service)], prefix="/churches", tags=["churches"]
)
router.add_api_route(
    "",
    churches.create_church,
    methods=["POST"],
    response_model=ChurchRead,
    status_code=status.HTTP_201_CREATED,
)
router.add_api_route("", churches.list_churches, methods=["GET"], response_model=list[ChurchRead])
