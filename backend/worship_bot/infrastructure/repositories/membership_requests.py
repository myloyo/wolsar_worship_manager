from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worship_bot.infrastructure.models import (
    ChurchMembershipRecord,
    ChurchMinistryRecord,
    MembershipRequestRecord,
    MinistryMembershipRecord,
    MinistryRoleRecord,
    UserMinistryRoleRecord,
    UserRecord,
)


class SqlMembershipRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def validate_roles(self, ministry_id: int, role_ids: list[int]) -> None:
        existing = set(
            await self.session.scalars(
                select(MinistryRoleRecord.id).where(
                    MinistryRoleRecord.church_ministry_id == ministry_id,
                    MinistryRoleRecord.id.in_(role_ids),
                )
            )
        )
        if existing != set(role_ids):
            raise ValueError("Выберите роли этого служения")

    async def apply(
        self, user_id: int, ministry_id: int, role_ids: list[int], message: str | None
    ) -> None:
        ministry = await self.session.scalar(
            select(ChurchMinistryRecord)
            .where(ChurchMinistryRecord.id == ministry_id)
            .with_for_update()
        )
        if ministry is None:
            raise LookupError("Служение не найдено")
        if await self.session.scalar(
            select(MinistryMembershipRecord.id).where(
                MinistryMembershipRecord.user_id == user_id,
                MinistryMembershipRecord.church_ministry_id == ministry_id,
            )
        ):
            raise ValueError("Вы уже состоите в этом служении")
        await self.validate_roles(ministry_id, role_ids)
        record = await self.session.scalar(
            select(MembershipRequestRecord).where(
                MembershipRequestRecord.user_id == user_id,
                MembershipRequestRecord.church_ministry_id == ministry_id,
            )
        )
        if record is None:
            record = MembershipRequestRecord(user_id=user_id, church_ministry_id=ministry_id)
            self.session.add(record)
        record.status, record.role_ids, record.message = (
            "pending",
            list(dict.fromkeys(role_ids)),
            message,
        )
        record.decision_note, record.decided_at, record.decided_by = None, None, None
        record.created_at = datetime.now(UTC)
        await self.session.commit()

    async def decide(
        self,
        actor_id: int,
        ministry_id: int,
        request_id: int,
        approve: bool,
        role_ids: list[int],
        note: str | None,
    ) -> None:
        ministry = await self.session.scalar(
            select(ChurchMinistryRecord)
            .where(ChurchMinistryRecord.id == ministry_id)
            .with_for_update()
        )
        record = await self.session.scalar(
            select(MembershipRequestRecord)
            .where(
                MembershipRequestRecord.id == request_id,
                MembershipRequestRecord.church_ministry_id == ministry_id,
            )
            .with_for_update()
        )
        if ministry is None or record is None:
            raise LookupError("Заявка не найдена")
        if record.status != "pending":
            raise ValueError("Заявка уже рассмотрена")
        if approve:
            await self.validate_roles(ministry_id, role_ids)
            user = await self.session.get(UserRecord, record.user_id)
            if user is None:
                raise LookupError("Пользователь не найден")
            if await self.session.scalar(
                select(MinistryMembershipRecord.id).where(
                    MinistryMembershipRecord.user_id == user.id,
                    MinistryMembershipRecord.church_ministry_id == ministry_id,
                )
            ):
                raise ValueError("Пользователь уже принят в служение")
            church_member = await self.session.scalar(
                select(ChurchMembershipRecord).where(
                    ChurchMembershipRecord.church_id == ministry.church_id,
                    ChurchMembershipRecord.user_id == user.id,
                )
            )
            if church_member is None:
                church_member = ChurchMembershipRecord(
                    church_id=ministry.church_id, user_id=user.id, access_level="member"
                )
                self.session.add(church_member)
                await self.session.flush()
            member = MinistryMembershipRecord(
                church_ministry_id=ministry_id, user_id=user.id, access_level="member"
            )
            self.session.add(member)
            await self.session.flush()
            for role_id in dict.fromkeys(role_ids):
                self.session.add(
                    UserMinistryRoleRecord(
                        church_membership_id=church_member.id,
                        ministry_membership_id=member.id,
                        ministry_role_id=role_id,
                    )
                )
            if user.church_id is None:
                user.church_id = ministry.church_id
        record.status = "approved" if approve else "rejected"
        record.decision_note, record.decided_by, record.decided_at = (
            note,
            actor_id,
            datetime.now(UTC),
        )
        await self.session.commit()
