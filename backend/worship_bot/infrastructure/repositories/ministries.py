import hashlib
import re

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from worship_bot.application.commands import RegistrationMinistry
from worship_bot.domain.entities import ChurchMinistry, MinistryRoleDefinition, MinistryType
from worship_bot.domain.worship_roles import WORSHIP_ROLES
from worship_bot.infrastructure.models import (
    ChurchMembershipRecord,
    ChurchMinistryRecord,
    MinistryMembershipRecord,
    MinistryRoleRecord,
    MinistryTypeRecord,
    UserMinistryRoleRecord,
    UserRecord,
)


class SqlMinistryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_catalog(self) -> list[MinistryType]:
        records = await self.session.scalars(
            select(MinistryTypeRecord).order_by(MinistryTypeRecord.name)
        )
        return [self.map_ministry_type(record) for record in records]

    async def list_church_ministries(self, church_id: int) -> list[ChurchMinistry]:
        records = await self.session.execute(
            select(ChurchMinistryRecord, MinistryTypeRecord)
            .join(
                MinistryTypeRecord, MinistryTypeRecord.id == ChurchMinistryRecord.ministry_type_id
            )
            .where(ChurchMinistryRecord.church_id == church_id)
            .order_by(MinistryTypeRecord.name)
        )
        return [
            self.map_church_ministry(church_ministry, ministry_type)
            for church_ministry, ministry_type in records
        ]

    async def get_church_ministry(self, church_ministry_id: int) -> ChurchMinistry | None:
        records = await self.session.execute(
            select(ChurchMinistryRecord, MinistryTypeRecord)
            .join(
                MinistryTypeRecord, MinistryTypeRecord.id == ChurchMinistryRecord.ministry_type_id
            )
            .where(ChurchMinistryRecord.id == church_ministry_id)
        )
        record = records.one_or_none()
        if record is None:
            return None
        return self.map_church_ministry(record[0], record[1])

    async def church_ministry_exists(self, church_id: int, church_ministry_id: int) -> bool:
        ministry_id = await self.session.scalar(
            select(ChurchMinistryRecord.id).where(
                ChurchMinistryRecord.id == church_ministry_id,
                ChurchMinistryRecord.church_id == church_id,
            )
        )
        return ministry_id is not None

    async def church_access_level(self, user_id: int, church_id: int) -> str | None:
        system_role = await self.session.scalar(
            select(UserRecord.system_role).where(UserRecord.id == user_id)
        )
        if system_role == "developer":
            return "developer"
        return await self.session.scalar(
            select(ChurchMembershipRecord.access_level).where(
                ChurchMembershipRecord.user_id == user_id,
                ChurchMembershipRecord.church_id == church_id,
            )
        )

    async def add_to_church(self, church_id: int, ministry_type_id: int) -> ChurchMinistry:
        existing = await self.session.scalar(
            select(ChurchMinistryRecord).where(
                ChurchMinistryRecord.church_id == church_id,
                ChurchMinistryRecord.ministry_type_id == ministry_type_id,
            )
        )
        if existing is None:
            existing = ChurchMinistryRecord(
                church_id=church_id,
                ministry_type_id=ministry_type_id,
            )
            self.session.add(existing)
            await self.session.flush()
        ministry_type = await self.session.get(MinistryTypeRecord, ministry_type_id)
        if ministry_type is None:
            raise LookupError(ministry_type_id)
        if ministry_type.code == "worship" or ministry_type.name.casefold() == "прославление":
            roles = list(
                await self.session.scalars(
                    select(MinistryRoleRecord).where(
                        MinistryRoleRecord.church_ministry_id == existing.id
                    )
                )
            )
            codes = {role.code for role in roles}
            names = {role.name.casefold() for role in roles}
            for code, name in WORSHIP_ROLES:
                if code not in codes and name.casefold() not in names:
                    self.session.add(
                        MinistryRoleRecord(
                            church_ministry_id=existing.id,
                            code=code,
                            name=name,
                        )
                    )
        await self.session.commit()
        return self.map_church_ministry(existing, ministry_type)

    async def get_catalog_type_by_name(self, name: str) -> MinistryType | None:
        record = await self.session.scalar(
            select(MinistryTypeRecord).where(func.lower(MinistryTypeRecord.name) == name.casefold())
        )
        return self.map_ministry_type(record) if record is not None else None

    async def create_catalog_type(
        self,
        name: str,
        created_by_user_id: int | None,
    ) -> MinistryType:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Ministry name cannot be empty")
        record = MinistryTypeRecord(
            code=self.slug(normalized_name),
            name=normalized_name,
            created_by_user_id=created_by_user_id,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return self.map_ministry_type(record)

    async def list_roles(self, church_ministry_id: int) -> list[MinistryRoleDefinition]:
        records = await self.session.scalars(
            select(MinistryRoleRecord)
            .where(MinistryRoleRecord.church_ministry_id == church_ministry_id)
            .order_by(MinistryRoleRecord.name)
        )
        return [self.map_role(record) for record in records]

    async def get_role_by_name(
        self,
        church_ministry_id: int,
        name: str,
    ) -> MinistryRoleDefinition | None:
        record = await self.session.scalar(
            select(MinistryRoleRecord).where(
                MinistryRoleRecord.church_ministry_id == church_ministry_id,
                func.lower(MinistryRoleRecord.name) == name.casefold(),
            )
        )
        return self.map_role(record) if record is not None else None

    async def create_role(
        self,
        church_ministry_id: int,
        name: str,
        created_by_user_id: int | None,
    ) -> MinistryRoleDefinition:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Role name cannot be empty")
        record = MinistryRoleRecord(
            church_ministry_id=church_ministry_id,
            code=self.slug(normalized_name),
            name=normalized_name,
            created_by_user_id=created_by_user_id,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return self.map_role(record)

    async def add_user_memberships(
        self,
        user_id: int,
        church_id: int,
        ministries: tuple[RegistrationMinistry, ...],
    ) -> None:
        church_membership = await self.session.scalar(
            select(ChurchMembershipRecord).where(
                ChurchMembershipRecord.user_id == user_id,
                ChurchMembershipRecord.church_id == church_id,
            )
        )
        if church_membership is None:
            church_membership = ChurchMembershipRecord(church_id=church_id, user_id=user_id)
            self.session.add(church_membership)
            await self.session.flush()

        for ministry in ministries:
            church_ministry = await self.session.get(
                ChurchMinistryRecord, ministry.church_ministry_id
            )
            if church_ministry is None or church_ministry.church_id != church_id:
                raise LookupError(ministry.church_ministry_id)
            ministry_membership = await self.session.scalar(
                select(MinistryMembershipRecord).where(
                    MinistryMembershipRecord.church_ministry_id == ministry.church_ministry_id,
                    MinistryMembershipRecord.user_id == user_id,
                )
            )
            if ministry_membership is None:
                ministry_membership = MinistryMembershipRecord(
                    church_ministry_id=ministry.church_ministry_id,
                    user_id=user_id,
                )
                self.session.add(ministry_membership)
                await self.session.flush()
            for role_name in ministry.role_names:
                role = await self.get_role_by_name(ministry.church_ministry_id, role_name)
                if role is None:
                    raise LookupError(role_name)
                existing = await self.session.scalar(
                    select(UserMinistryRoleRecord.id).where(
                        UserMinistryRoleRecord.ministry_membership_id == ministry_membership.id,
                        UserMinistryRoleRecord.ministry_role_id == role.id,
                    )
                )
                if existing is None:
                    self.session.add(
                        UserMinistryRoleRecord(
                            church_membership_id=church_membership.id,
                            ministry_membership_id=ministry_membership.id,
                            ministry_role_id=role.id,
                        )
                    )
        await self.session.flush()

    async def access_level(self, user_id: int, church_ministry_id: int) -> str | None:
        system_role = await self.session.scalar(
            select(UserRecord.system_role).where(UserRecord.id == user_id)
        )
        if system_role == "developer":
            return "developer"
        return await self.session.scalar(
            select(MinistryMembershipRecord.access_level).where(
                MinistryMembershipRecord.user_id == user_id,
                MinistryMembershipRecord.church_ministry_id == church_ministry_id,
            )
        )

    async def set_access_level(
        self,
        user_id: int,
        church_ministry_id: int,
        access_level: str,
    ) -> bool:
        await self.session.scalar(
            select(ChurchMinistryRecord)
            .where(ChurchMinistryRecord.id == church_ministry_id)
            .with_for_update()
        )
        membership = await self.session.scalar(
            select(MinistryMembershipRecord).where(
                MinistryMembershipRecord.user_id == user_id,
                MinistryMembershipRecord.church_ministry_id == church_ministry_id,
            )
        )
        if membership is None:
            return False
        if membership.access_level == "admin" and access_level != "admin":
            admin_count = await self.session.scalar(
                select(func.count())
                .select_from(MinistryMembershipRecord)
                .where(
                    MinistryMembershipRecord.church_ministry_id == church_ministry_id,
                    MinistryMembershipRecord.access_level == "admin",
                )
            )
            if admin_count is None or admin_count < 2:
                raise ValueError("Сначала назначьте другого администратора служения")
        membership.access_level = access_level
        await self.session.commit()
        return True

    async def can_edit_song_set(self, user_id: int, church_ministry_id: int) -> bool:
        access = await self.access_level(user_id, church_ministry_id)
        if access in {"coordinator", "admin", "developer"}:
            return True
        role_membership_id = await self.session.scalar(
            select(UserMinistryRoleRecord.id)
            .join(
                MinistryRoleRecord,
                MinistryRoleRecord.id == UserMinistryRoleRecord.ministry_role_id,
            )
            .join(
                MinistryMembershipRecord,
                MinistryMembershipRecord.id == UserMinistryRoleRecord.ministry_membership_id,
            )
            .where(
                MinistryMembershipRecord.user_id == user_id,
                MinistryMembershipRecord.church_ministry_id == church_ministry_id,
                (MinistryRoleRecord.code == "lead_vocal")
                | MinistryRoleRecord.code.like("back_vocal%"),
            )
        )
        return role_membership_id is not None

    async def add_user_role(
        self,
        user_id: int,
        church_ministry_id: int,
        ministry_role_id: int,
    ) -> None:
        ministry = await self.session.get(ChurchMinistryRecord, church_ministry_id)
        if ministry is None:
            raise LookupError(church_ministry_id)
        church_membership = await self.session.scalar(
            select(ChurchMembershipRecord).where(
                ChurchMembershipRecord.user_id == user_id,
                ChurchMembershipRecord.church_id == ministry.church_id,
            )
        )
        if church_membership is None:
            church_membership = ChurchMembershipRecord(
                user_id=user_id,
                church_id=ministry.church_id,
            )
            self.session.add(church_membership)
            await self.session.flush()
        membership = await self.session.scalar(
            select(MinistryMembershipRecord).where(
                MinistryMembershipRecord.user_id == user_id,
                MinistryMembershipRecord.church_ministry_id == church_ministry_id,
            )
        )
        if membership is None:
            membership = MinistryMembershipRecord(
                user_id=user_id,
                church_ministry_id=church_ministry_id,
            )
            self.session.add(membership)
            await self.session.flush()
        await self.session.execute(
            insert(UserMinistryRoleRecord)
            .values(
                church_membership_id=church_membership.id,
                ministry_membership_id=membership.id,
                ministry_role_id=ministry_role_id,
            )
            .on_conflict_do_nothing()
        )
        await self.session.commit()

    @staticmethod
    def slug(value: str) -> str:
        normalized = re.sub(r"[^\w]+", "_", value.casefold(), flags=re.UNICODE).strip("_")
        digest = hashlib.sha1(value.casefold().encode("utf-8")).hexdigest()[:8]
        return f"{normalized[:54] or 'item'}_{digest}"

    @staticmethod
    def map_ministry_type(record: MinistryTypeRecord) -> MinistryType:
        return MinistryType(record.id, record.code, record.name, record.created_by_user_id)

    @staticmethod
    def map_church_ministry(
        church_ministry: ChurchMinistryRecord,
        ministry_type: MinistryTypeRecord,
    ) -> ChurchMinistry:
        return ChurchMinistry(
            id=church_ministry.id,
            church_id=church_ministry.church_id,
            ministry_type_id=church_ministry.ministry_type_id,
            ministry_type_code=ministry_type.code,
            ministry_type_name=ministry_type.name,
        )

    @staticmethod
    def map_role(record: MinistryRoleRecord) -> MinistryRoleDefinition:
        return MinistryRoleDefinition(
            id=record.id,
            church_ministry_id=record.church_ministry_id,
            code=record.code,
            name=record.name,
            created_by_user_id=record.created_by_user_id,
        )
