from datetime import date, datetime, timedelta

from worship_bot.application.commands import AdvanceRegistration, StartRegistration
from worship_bot.application.exceptions import (
    ChurchNotFoundError,
    ConsentRequiredError,
    ExternalAccountAlreadyLinkedError,
    RegistrationDraftNotFoundError,
    RegistrationStepError,
)
from worship_bot.application.repositories import (
    ChurchRepository,
    IdentityRepository,
    MinistryRepository,
)
from worship_bot.domain.entities import RegistrationDraft
from worship_bot.domain.enums import IdentityProvider, RegistrationStep


class RegistrationService:
    steps = (
        RegistrationStep.CHURCH,
        RegistrationStep.NAME,
        RegistrationStep.BIRTHDAY,
        RegistrationStep.MINISTRIES,
        RegistrationStep.ROLES,
        RegistrationStep.CONSENT,
        RegistrationStep.REVIEW,
    )

    def __init__(
        self,
        identity_repository: IdentityRepository,
        ministry_repository: MinistryRepository,
        church_repository: ChurchRepository,
        consent_version: str,
        draft_lifetime: timedelta = timedelta(days=1),
    ) -> None:
        self.identity_repository = identity_repository
        self.ministry_repository = ministry_repository
        self.church_repository = church_repository
        self.consent_version = consent_version
        self.draft_lifetime = draft_lifetime

    async def start(self, command: StartRegistration) -> RegistrationDraft:
        if await self.identity_repository.external_account_exists(
            command.provider, command.external_user_id
        ):
            raise ExternalAccountAlreadyLinkedError(command.external_user_id)
        return await self.identity_repository.start_registration(command)

    async def advance(self, command: AdvanceRegistration) -> RegistrationDraft:
        draft = await self.owned_draft(command.draft_id, command.provider, command.external_user_id)
        if draft.current_step != command.step or command.step not in self.steps[:-1]:
            raise RegistrationStepError(f"Expected step {draft.current_step.value}")

        data = dict(draft.registration_data)
        next_step = self.steps[self.steps.index(command.step) + 1]
        if command.step == RegistrationStep.CHURCH:
            church_id = self.positive_int(command.answers.get("church_id"), "church_id")
            if not await self.church_repository.exists(church_id):
                raise ChurchNotFoundError(church_id)
            data["church_id"] = church_id
        elif command.step == RegistrationStep.NAME:
            data["name"] = self.required_text(command.answers.get("name"), "name", 100)
            data["surname"] = self.required_text(command.answers.get("surname"), "surname", 100)
        elif command.step == RegistrationStep.BIRTHDAY:
            birthday_text = self.required_text(command.answers.get("birthday"), "birthday", 10)
            try:
                birthday = datetime.strptime(birthday_text, "%d.%m.%Y").date()
            except ValueError as error:
                raise RegistrationStepError("Birthday must use DD.MM.YYYY format") from error
            if birthday > date.today():
                raise RegistrationStepError("Birthday cannot be in the future")
            data["birthday_date"] = birthday.isoformat()
        elif command.step == RegistrationStep.MINISTRIES:
            raw_names = command.answers.get("ministries")
            if not isinstance(raw_names, list) or not raw_names:
                raise RegistrationStepError("Select at least one ministry")
            church_id = self.positive_int(data.get("church_id"), "church_id")
            selected: list[dict[str, object]] = []
            seen_names: set[str] = set()
            for raw_name in raw_names:
                name = self.required_text(raw_name, "ministry name", 150)
                if name.casefold() in seen_names:
                    continue
                seen_names.add(name.casefold())
                ministry_type = await self.ministry_repository.get_catalog_type_by_name(name)
                if ministry_type is None:
                    ministry_type = await self.ministry_repository.create_catalog_type(name, None)
                church_ministry = await self.ministry_repository.add_to_church(
                    church_id, ministry_type.id
                )
                selected.append(
                    {"church_ministry_id": church_ministry.id, "name": ministry_type.name}
                )
            data["ministries"] = selected
        elif command.step == RegistrationStep.ROLES:
            selected_ministries = data.get("ministries")
            raw_roles = command.answers.get("roles")
            if not isinstance(selected_ministries, list) or not isinstance(raw_roles, list):
                raise RegistrationStepError("Roles must be provided for selected ministries")
            roles_by_ministry: dict[int, list[str]] = {}
            for item in raw_roles:
                if not isinstance(item, dict):
                    raise RegistrationStepError("Each role selection must identify a ministry")
                ministry_id = self.positive_int(
                    item.get("church_ministry_id"), "church_ministry_id"
                )
                role_names = item.get("role_names")
                if not isinstance(role_names, list) or not role_names:
                    raise RegistrationStepError("Select at least one role for each ministry")
                roles_by_ministry[ministry_id] = [
                    self.required_text(role_name, "role name", 100) for role_name in role_names
                ]
            selected_ids = {
                self.positive_int(item.get("church_ministry_id"), "church_ministry_id")
                for item in selected_ministries
                if isinstance(item, dict)
            }
            if set(roles_by_ministry) != selected_ids:
                raise RegistrationStepError("Provide roles for every selected ministry")
            memberships: list[dict[str, object]] = []
            for ministry_id, role_names in roles_by_ministry.items():
                role_ids: list[int] = []
                for role_name in role_names:
                    role = await self.ministry_repository.get_role_by_name(ministry_id, role_name)
                    if role is None:
                        raise RegistrationStepError("Выберите роль из справочника служения")
                    role_ids.append(role.id)
                memberships.append({"church_ministry_id": ministry_id, "role_ids": role_ids})
            data["selected_roles"] = memberships
        elif command.step == RegistrationStep.CONSENT:
            if command.answers.get("accepted") is not True:
                raise ConsentRequiredError("Registration requires explicit consent acceptance")
            data["consent_policy_version"] = self.consent_version

        return await self.identity_repository.save_registration_step(draft, next_step, data)

    async def review(
        self,
        draft_id: int,
        provider: IdentityProvider,
        external_user_id: str,
    ) -> RegistrationDraft:
        draft = await self.owned_draft(draft_id, provider, external_user_id)
        if draft.current_step != RegistrationStep.REVIEW:
            raise RegistrationStepError("Registration is not ready for review")
        return draft

    async def confirm(
        self,
        draft_id: int,
        provider: IdentityProvider,
        external_user_id: str,
    ) -> int:
        draft = await self.review(draft_id, provider, external_user_id)
        if draft.registration_data.get("consent_policy_version") != self.consent_version:
            raise ConsentRequiredError("Consent must be accepted for the current policy version")
        return await self.identity_repository.complete_registration(draft)

    async def owned_draft(
        self,
        draft_id: int,
        provider: IdentityProvider,
        external_user_id: str,
    ) -> RegistrationDraft:
        draft = await self.identity_repository.get_registration_draft(
            draft_id, provider, external_user_id
        )
        if draft is None or draft.status != "pending":
            raise RegistrationDraftNotFoundError(draft_id)
        return draft

    @staticmethod
    def required_text(value: object, field_name: str, max_length: int) -> str:
        if not isinstance(value, str):
            raise RegistrationStepError(f"{field_name} must be text")
        normalized = value.strip()
        if not normalized or len(normalized) > max_length:
            raise RegistrationStepError(f"{field_name} must contain 1-{max_length} characters")
        return normalized

    @staticmethod
    def positive_int(value: object, field_name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise RegistrationStepError(f"{field_name} must be a positive integer")
        return value
