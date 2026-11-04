import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from worship_bot.application.exceptions import AccessDeniedError, ParticipantNotFoundError
from worship_bot.domain.portal import (
    LoginTicket,
    Member,
    MemberRole,
    MinistrySummary,
    Profile,
    permissions_for,
)
from worship_bot.infrastructure.models import (
    ChurchMinistryRecord,
    ChurchRecord,
    ExternalAccountRecord,
    MinistryMembershipRecord,
    MinistryRoleRecord,
    MinistryTypeRecord,
    UserMinistryRoleRecord,
    UserRecord,
)
from worship_bot.infrastructure.models.portal import LoginCodeRecord
from worship_bot.infrastructure.models.web_push import PushSubscriptionRecord
from worship_bot.infrastructure.repositories.ministries import SqlMinistryRepository


class SqlPortalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def require_permission(self, user_id: int, ministry_id: int, permission: str) -> None:
        access = await SqlMinistryRepository(self.session).access_level(user_id, ministry_id)
        if permission not in permissions_for(access):
            raise AccessDeniedError("Недостаточно прав в этом служении")

    async def profile(self, user_id: int) -> Profile:
        user = await self.session.get(UserRecord, user_id)
        if user is None:
            raise ParticipantNotFoundError(user_id)
        query = (
            select(
                ChurchMinistryRecord.id,
                MinistryTypeRecord.name,
                ChurchRecord.name.label("church_name"),
                MinistryMembershipRecord.access_level,
            )
            .select_from(ChurchMinistryRecord)
            .join(
                MinistryTypeRecord, MinistryTypeRecord.id == ChurchMinistryRecord.ministry_type_id
            )
            .join(ChurchRecord, ChurchRecord.id == ChurchMinistryRecord.church_id)
            .outerjoin(
                MinistryMembershipRecord,
                (MinistryMembershipRecord.church_ministry_id == ChurchMinistryRecord.id)
                & (MinistryMembershipRecord.user_id == user_id),
            )
        )
        if user.system_role != "developer":
            query = query.where(MinistryMembershipRecord.user_id == user_id)
        rows = await self.session.execute(query.order_by(ChurchMinistryRecord.id))
        ministries = []
        for row in rows:
            access = "developer" if user.system_role == "developer" else row.access_level
            ministries.append(
                MinistrySummary(row.id, row.name, row.church_name, access, permissions_for(access))
            )
        return Profile(user.id, user.name, user.surname, user.birthday_date, ministries)

    async def members(self, ministry_id: int) -> list[Member]:
        rows = await self.session.execute(
            select(UserRecord, MinistryMembershipRecord)
            .join(MinistryMembershipRecord, MinistryMembershipRecord.user_id == UserRecord.id)
            .where(MinistryMembershipRecord.church_ministry_id == ministry_id)
            .order_by(UserRecord.name)
        )
        role_rows = await self.session.execute(
            select(
                MinistryMembershipRecord.user_id,
                MinistryRoleRecord,
                UserMinistryRoleRecord.id,
                UserMinistryRoleRecord.allowed_event_kinds,
            )
            .select_from(MinistryMembershipRecord)
            .join(
                UserMinistryRoleRecord,
                UserMinistryRoleRecord.ministry_membership_id == MinistryMembershipRecord.id,
            )
            .join(
                MinistryRoleRecord, MinistryRoleRecord.id == UserMinistryRoleRecord.ministry_role_id
            )
            .where(MinistryMembershipRecord.church_ministry_id == ministry_id)
        )
        roles: dict[int, list[MemberRole]] = {}
        for user_id, role, user_role_id, allowed_kinds in role_rows:
            roles.setdefault(user_id, []).append(
                MemberRole(role.id, role.name, user_role_id, allowed_kinds)
            )
        push_rows = await self.session.execute(
            select(PushSubscriptionRecord.user_id, func.max(PushSubscriptionRecord.checked_at))
            .where(PushSubscriptionRecord.enabled.is_(True))
            .group_by(PushSubscriptionRecord.user_id)
        )
        push_checks = {user_id: checked_at for user_id, checked_at in push_rows}
        return [
            Member(
                user.id,
                user.name,
                user.surname,
                membership.access_level,
                roles.get(user.id, []),
                (
                    "needs_check"
                    if push_checks[user.id].replace(tzinfo=UTC)
                    < datetime.now(UTC) - timedelta(days=30)
                    else "enabled"
                )
                if user.id in push_checks
                else "needs_setup",
                push_checks.get(user.id),
            )
            for user, membership in rows
        ]

    async def external_user(self, provider: str, external_id: str) -> int | None:
        value = await self.session.scalar(
            select(ExternalAccountRecord.user_id).where(
                ExternalAccountRecord.provider == provider,
                ExternalAccountRecord.external_user_id == external_id,
            )
        )
        return int(value) if value is not None else None

    async def issue_login(self, user_id: int) -> LoginTicket:
        code = secrets.token_urlsafe(24)
        expires_at = datetime.now(UTC) + timedelta(minutes=5)
        self.session.add(
            LoginCodeRecord(
                code_hash=hashlib.sha256(code.encode()).hexdigest(),
                user_id=user_id,
                expires_at=expires_at,
            )
        )
        await self.session.commit()
        return LoginTicket(code, expires_at)

    async def exchange_login(self, code: str) -> int | None:
        now = datetime.now(UTC)
        user_id = await self.session.scalar(
            update(LoginCodeRecord)
            .where(
                LoginCodeRecord.code_hash == hashlib.sha256(code.encode()).hexdigest(),
                LoginCodeRecord.used_at.is_(None),
                LoginCodeRecord.expires_at > now,
            )
            .values(used_at=now)
            .returning(LoginCodeRecord.user_id)
        )
        await self.session.commit()
        return int(user_id) if user_id is not None else None
