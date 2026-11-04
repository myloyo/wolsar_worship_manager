from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worship_bot.application.commands import StartRegistration
from worship_bot.application.exceptions import (
    ExternalAccountAlreadyLinkedError,
    RegistrationDraftNotFoundError,
    RegistrationStepError,
)
from worship_bot.domain.entities import RegistrationDraft
from worship_bot.domain.enums import IdentityProvider, RegistrationStep
from worship_bot.infrastructure.models import (
    ChurchMembershipRecord,
    ChurchMinistryRecord,
    ConsentAcceptanceRecord,
    ExternalAccountRecord,
    MinistryMembershipRecord,
    MinistryRoleRecord,
    RegistrationDraftRecord,
    UserMinistryRoleRecord,
    UserRecord,
)


class SqlIdentityRepository:
    def __init__(
        self,
        session: AsyncSession,
        draft_lifetime: timedelta,
        initial_developer_provider: str | None = None,
        initial_developer_external_user_id: str | None = None,
    ) -> None:
        self.session = session
        self.draft_lifetime = draft_lifetime
        self.initial_developer_provider = initial_developer_provider
        self.initial_developer_external_user_id = initial_developer_external_user_id

    async def external_account_exists(
        self,
        provider: IdentityProvider,
        external_user_id: str,
    ) -> bool:
        account_id = await self.session.scalar(
            select(ExternalAccountRecord.id).where(
                ExternalAccountRecord.provider == provider.value,
                ExternalAccountRecord.external_user_id == external_user_id,
            )
        )
        return account_id is not None

    async def get_user_id_for_external_account(
        self,
        provider: IdentityProvider,
        external_user_id: str,
    ) -> int | None:
        return await self.session.scalar(
            select(ExternalAccountRecord.user_id).where(
                ExternalAccountRecord.provider == provider.value,
                ExternalAccountRecord.external_user_id == external_user_id,
            )
        )

    async def start_registration(self, command: StartRegistration) -> RegistrationDraft:
        record = await self.session.scalar(
            select(RegistrationDraftRecord).where(
                RegistrationDraftRecord.provider == command.provider.value,
                RegistrationDraftRecord.external_user_id == command.external_user_id,
            )
        )
        expires_at = datetime.now(UTC) + self.draft_lifetime
        if record is None:
            record = RegistrationDraftRecord(
                provider=command.provider.value,
                external_user_id=command.external_user_id,
                external_username=command.external_username,
                current_step=RegistrationStep.CHURCH.value,
                status="pending",
                registration_data={},
                expires_at=expires_at,
            )
            self.session.add(record)
        elif record.status == "pending" and record.expires_at > datetime.now(UTC):
            record.external_username = command.external_username
            record.expires_at = expires_at
        else:
            record.external_username = command.external_username
            record.current_step = RegistrationStep.CHURCH.value
            record.status = "pending"
            record.registration_data = {}
            record.expires_at = expires_at
        await self.session.commit()
        await self.session.refresh(record)
        return self.map_draft(record)

    async def get_registration_draft(
        self,
        draft_id: int,
        provider: IdentityProvider,
        external_user_id: str,
    ) -> RegistrationDraft | None:
        record = await self.session.scalar(
            select(RegistrationDraftRecord).where(
                RegistrationDraftRecord.id == draft_id,
                RegistrationDraftRecord.provider == provider.value,
                RegistrationDraftRecord.external_user_id == external_user_id,
                RegistrationDraftRecord.expires_at > datetime.now(UTC),
            )
        )
        return self.map_draft(record) if record is not None else None

    async def save_registration_step(
        self,
        draft: RegistrationDraft,
        step: RegistrationStep,
        data: dict[str, object],
    ) -> RegistrationDraft:
        record = await self.session.get(RegistrationDraftRecord, draft.id)
        if record is None or record.status != "pending":
            raise RegistrationDraftNotFoundError(draft.id)
        record.current_step = step.value
        record.registration_data = data
        await self.session.commit()
        await self.session.refresh(record)
        return self.map_draft(record)

    async def complete_registration(self, draft: RegistrationDraft) -> int:
        record = await self.session.get(RegistrationDraftRecord, draft.id)
        if record is None or record.status != "pending":
            raise RegistrationDraftNotFoundError(draft.id)
        if await self.external_account_exists(draft.provider, draft.external_user_id):
            raise ExternalAccountAlreadyLinkedError(draft.external_user_id)

        data = record.registration_data
        church_id = self.required_int(data.get("church_id"), "church_id")
        name = self.required_text(data.get("name"), "name")
        surname = self.required_text(data.get("surname"), "surname")
        birthday_date = datetime.strptime(
            self.required_text(data.get("birthday_date"), "birthday_date"), "%Y-%m-%d"
        ).date()
        consent_version = self.required_text(
            data.get("consent_policy_version"), "consent_policy_version"
        )
        raw_roles = data.get("selected_roles")
        if not isinstance(raw_roles, list):
            raise RegistrationStepError("Selected ministry roles are missing")

        is_initial_developer = (
            draft.provider.value == self.initial_developer_provider
            and draft.external_user_id == self.initial_developer_external_user_id
            and self.initial_developer_external_user_id is not None
        )
        initial_access_level = "developer" if is_initial_developer else "member"
        user = UserRecord(
            name=name,
            surname=surname,
            church_id=church_id,
            birthday_date=birthday_date,
            system_role=initial_access_level,
            consent_approved=True,
        )
        self.session.add(user)
        await self.session.flush()

        church_membership = ChurchMembershipRecord(
            church_id=church_id,
            user_id=user.id,
            access_level=initial_access_level,
        )
        self.session.add(church_membership)
        await self.session.flush()

        for item in raw_roles:
            if not isinstance(item, dict):
                raise RegistrationStepError("Selected ministry role entry is invalid")
            church_ministry_id = self.required_int(
                item.get("church_ministry_id"), "church_ministry_id"
            )
            valid_ministry_id = await self.session.scalar(
                select(ChurchMinistryRecord.id).where(
                    ChurchMinistryRecord.id == church_ministry_id,
                    ChurchMinistryRecord.church_id == church_id,
                )
            )
            if valid_ministry_id is None:
                raise RegistrationStepError("Selected ministry does not belong to the church")
            role_ids = item.get("role_ids")
            if not isinstance(role_ids, list) or not role_ids:
                raise RegistrationStepError("At least one role is required for each ministry")
            ministry_membership = MinistryMembershipRecord(
                church_ministry_id=church_ministry_id,
                user_id=user.id,
                access_level=initial_access_level,
            )
            self.session.add(ministry_membership)
            await self.session.flush()
            for role_id_value in role_ids:
                role_id = self.required_int(role_id_value, "ministry_role_id")
                valid_role_id = await self.session.scalar(
                    select(MinistryRoleRecord.id).where(
                        MinistryRoleRecord.id == role_id,
                        MinistryRoleRecord.church_ministry_id == church_ministry_id,
                    )
                )
                if valid_role_id is None:
                    raise RegistrationStepError("Selected role does not belong to the ministry")
                self.session.add(
                    UserMinistryRoleRecord(
                        church_membership_id=church_membership.id,
                        ministry_membership_id=ministry_membership.id,
                        ministry_role_id=role_id,
                    )
                )

        self.session.add(
            ExternalAccountRecord(
                user_id=user.id,
                provider=draft.provider.value,
                external_user_id=draft.external_user_id,
                username=draft.external_username,
                verified_at=datetime.now(UTC),
            )
        )
        self.session.add(
            ConsentAcceptanceRecord(
                user_id=user.id,
                policy_version=consent_version,
                provider=draft.provider.value,
            )
        )
        record.status = "completed"
        record.current_step = RegistrationStep.COMPLETED.value
        await self.session.commit()
        return user.id

    @staticmethod
    def map_draft(record: RegistrationDraftRecord) -> RegistrationDraft:
        return RegistrationDraft(
            id=record.id,
            provider=IdentityProvider(record.provider),
            external_user_id=record.external_user_id,
            external_username=record.external_username,
            current_step=RegistrationStep(record.current_step),
            status=record.status,
            registration_data=dict(record.registration_data),
        )

    @staticmethod
    def required_text(value: object, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise RegistrationStepError(f"{field} is missing")
        return value.strip()

    @staticmethod
    def required_int(value: object, field: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise RegistrationStepError(f"{field} is invalid")
        return value
