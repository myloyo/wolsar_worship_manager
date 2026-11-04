from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from worship_bot.api.membership_schemas import (
    BotJoinRequest,
    DirectoryChurch,
    DirectoryRole,
    DirectoryTeam,
    JoinDecision,
    JoinRequest,
    MembershipRequestRead,
)
from worship_bot.api.routers.portal import CurrentUser, Session, require_portal_permission
from worship_bot.api.schemas import BotIdentity
from worship_bot.api.security import require_bot_service
from worship_bot.infrastructure.models import (
    ChurchMinistryRecord,
    ChurchRecord,
    MembershipRequestRecord,
    MinistryMembershipRecord,
    MinistryRoleRecord,
    MinistryTypeRecord,
    UserRecord,
)
from worship_bot.infrastructure.repositories.membership_requests import (
    SqlMembershipRequestRepository,
)
from worship_bot.infrastructure.repositories.portal import SqlPortalRepository

router = APIRouter(prefix="/portal", tags=["membership applications"])


@router.get("/directory", response_model=list[DirectoryChurch])
async def directory(user_id: CurrentUser, session: Session) -> list[DirectoryChurch]:
    churches = list(await session.scalars(select(ChurchRecord).order_by(ChurchRecord.name)))
    rows = (
        await session.execute(
            select(ChurchMinistryRecord, MinistryTypeRecord.name)
            .join(
                MinistryTypeRecord, MinistryTypeRecord.id == ChurchMinistryRecord.ministry_type_id
            )
            .order_by(MinistryTypeRecord.name)
        )
    ).all()
    memberships = set(
        await session.scalars(
            select(MinistryMembershipRecord.church_ministry_id).where(
                MinistryMembershipRecord.user_id == user_id
            )
        )
    )
    applications = {
        record.church_ministry_id: record
        for record in await session.scalars(
            select(MembershipRequestRecord).where(MembershipRequestRecord.user_id == user_id)
        )
    }
    roles = list(await session.scalars(select(MinistryRoleRecord)))
    available = set(
        await session.scalars(
            select(MinistryMembershipRecord.church_ministry_id).where(
                MinistryMembershipRecord.access_level == "admin"
            )
        )
    )
    developer = await session.scalar(
        select(UserRecord.id).where(UserRecord.system_role == "developer").limit(1)
    )

    result = []
    for church in churches:
        teams = []
        for team, name in rows:
            if team.church_id != church.id or (team.id not in available and developer is None):
                continue
            application = applications.get(team.id)
            status = (
                "member"
                if team.id in memberships
                else (
                    application.status
                    if application and application.status in {"pending", "rejected"}
                    else "none"
                )
            )
            teams.append(
                DirectoryTeam(
                    id=team.id,
                    name=name,
                    status=status,
                    decision_note=application.decision_note if application else None,
                    roles=[
                        DirectoryRole(id=role.id, name=role.name)
                        for role in roles
                        if role.church_ministry_id == team.id
                    ],
                )
            )
        if teams:
            result.append(DirectoryChurch(id=church.id, name=church.name, teams=teams))
    return result


@router.post("/ministries/{ministry_id}/applications", status_code=204)
async def apply(
    ministry_id: int, payload: JoinRequest, user_id: CurrentUser, session: Session
) -> None:
    try:
        await SqlMembershipRequestRepository(session).apply(
            user_id, ministry_id, payload.role_ids, payload.message
        )
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/ministries/{ministry_id}/applications", response_model=list[MembershipRequestRead])
async def applications(
    ministry_id: int, user_id: CurrentUser, session: Session
) -> list[MembershipRequestRead]:
    await require_portal_permission(session, user_id, ministry_id, "manage_members")
    rows = await session.execute(
        select(MembershipRequestRecord, UserRecord)
        .join(UserRecord, UserRecord.id == MembershipRequestRecord.user_id)
        .where(
            MembershipRequestRecord.church_ministry_id == ministry_id,
            MembershipRequestRecord.status == "pending",
        )
        .order_by(MembershipRequestRecord.created_at)
    )
    return [
        MembershipRequestRead(
            id=record.id,
            user_id=user.id,
            name=user.name,
            surname=user.surname,
            role_ids=record.role_ids,
            message=record.message,
            created_at=record.created_at,
        )
        for record, user in rows
    ]


@router.put("/ministries/{ministry_id}/applications/{request_id}", status_code=204)
async def decide(
    ministry_id: int, request_id: int, payload: JoinDecision, user_id: CurrentUser, session: Session
) -> None:
    await require_portal_permission(session, user_id, ministry_id, "manage_members")
    try:
        await SqlMembershipRequestRepository(session).decide(
            user_id, ministry_id, request_id, payload.approve, payload.role_ids, payload.message
        )
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


internal_router = APIRouter(
    prefix="/internal/bot", dependencies=[Depends(require_bot_service)], tags=["bot applications"]
)


async def linked_user(payload: BotIdentity, session: Session) -> int:
    user_id = await SqlPortalRepository(session).external_user(
        payload.provider.value, payload.external_user_id
    )
    if user_id is None:
        raise HTTPException(404, "Сначала привяжите Telegram в личной карточке на сайте")
    return user_id


@internal_router.post("/directory", response_model=list[DirectoryChurch])
async def bot_directory(payload: BotIdentity, session: Session) -> list[DirectoryChurch]:
    return await directory(await linked_user(payload, session), session)


@internal_router.post("/applications", status_code=204)
async def bot_apply(payload: BotJoinRequest, session: Session) -> None:
    await apply(
        payload.church_ministry_id,
        JoinRequest(role_ids=payload.role_ids, message=payload.message),
        await linked_user(payload, session),
        session,
    )
