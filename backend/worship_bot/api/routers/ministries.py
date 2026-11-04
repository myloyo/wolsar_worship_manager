from fastapi import APIRouter, status

from worship_bot.api.handlers import ministries
from worship_bot.api.schemas import (
    ChurchMinistryRead,
    MinistryRoleRead,
    MinistryTypeRead,
)

router = APIRouter(tags=["ministries"])
router.add_api_route(
    "/ministries/catalog",
    ministries.list_catalog,
    methods=["GET"],
    response_model=list[MinistryTypeRead],
)
router.add_api_route(
    "/churches/{church_id}/ministries",
    ministries.list_church_ministries,
    methods=["GET"],
    response_model=list[ChurchMinistryRead],
)
router.add_api_route(
    "/churches/{church_id}/ministries",
    ministries.add_ministry_to_church,
    methods=["POST"],
    response_model=ChurchMinistryRead,
    status_code=status.HTTP_201_CREATED,
)
router.add_api_route(
    "/church-ministries/{church_ministry_id}/roles",
    ministries.list_roles,
    methods=["GET"],
    response_model=list[MinistryRoleRead],
)
router.add_api_route(
    "/church-ministries/{church_ministry_id}/roles",
    ministries.create_role,
    methods=["POST"],
    response_model=MinistryRoleRead,
    status_code=status.HTTP_201_CREATED,
)
router.add_api_route(
    "/church-ministries/{church_ministry_id}/roles/self",
    ministries.create_role_for_self,
    methods=["POST"],
    response_model=MinistryRoleRead,
    status_code=status.HTTP_201_CREATED,
)
