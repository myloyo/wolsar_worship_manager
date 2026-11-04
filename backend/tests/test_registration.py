from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from hamcrest import assert_that, equal_to
from worship_bot.application.commands import (
    AdvanceRegistration,
    NewParticipant,
    StartRegistration,
)
from worship_bot.application.exceptions import (
    ChurchNotFoundError,
    ConsentRequiredError,
    ExternalAccountAlreadyLinkedError,
    RegistrationDraftNotFoundError,
    RegistrationStepError,
)
from worship_bot.application.services import ParticipantService, RegistrationService
from worship_bot.domain.entities import ChurchMinistry, MinistryType, RegistrationDraft
from worship_bot.domain.enums import RegistrationStep, WorshipRole


async def test_register_participant_keeps_profile_and_roles(
    participant_service: ParticipantService,
    sample_participant: NewParticipant,
) -> None:
    # Act
    participant = await participant_service.register(sample_participant)

    # Assert
    assert_that(participant.name, equal_to("Анна"))
    assert_that(participant.worship_roles, equal_to((WorshipRole.BACK_VOCAL,)))
    assert_that(participant.consent_approved, equal_to(True))


async def test_register_participant_requires_consent(
    participant_service: ParticipantService,
    sample_participant: NewParticipant,
) -> None:
    # Arrange
    request = NewParticipant(
        name=sample_participant.name,
        surname=sample_participant.surname,
        church_id=sample_participant.church_id,
        birthday_date=sample_participant.birthday_date,
        consent_approved=False,
        worship_roles=sample_participant.worship_roles,
    )

    # Act / Assert
    with pytest.raises(ConsentRequiredError):
        await participant_service.register(request)


async def test_register_participant_rejects_unknown_church(
    participant_service: ParticipantService,
    sample_participant: NewParticipant,
) -> None:
    # Arrange
    request = NewParticipant(
        name=sample_participant.name,
        surname=sample_participant.surname,
        church_id=404,
        birthday_date=sample_participant.birthday_date,
        consent_approved=True,
        worship_roles=sample_participant.worship_roles,
    )

    # Act / Assert
    with pytest.raises(ChurchNotFoundError):
        await participant_service.register(request)


async def test_start_registration_creates_draft(
    registration_service: RegistrationService,
    registration_repositories: tuple[AsyncMock, AsyncMock, AsyncMock],
    registration_identity: StartRegistration,
    registration_draft: RegistrationDraft,
) -> None:
    # Arrange
    identity_repository = registration_repositories[0]
    identity_repository.external_account_exists.return_value = False
    identity_repository.start_registration.return_value = registration_draft

    # Act
    result = await registration_service.start(registration_identity)

    # Assert
    assert_that(result.id, equal_to(registration_draft.id))
    identity_repository.start_registration.assert_awaited_once_with(registration_identity)


async def test_start_registration_rejects_already_linked_platform_account(
    registration_service: RegistrationService,
    registration_repositories: tuple[AsyncMock, AsyncMock, AsyncMock],
    registration_identity: StartRegistration,
) -> None:
    # Arrange
    identity_repository = registration_repositories[0]
    identity_repository.external_account_exists.return_value = True

    # Act / Assert
    with pytest.raises(ExternalAccountAlreadyLinkedError):
        await registration_service.start(registration_identity)

    # Assert
    identity_repository.start_registration.assert_not_awaited()


async def test_registration_step_requires_owned_draft(
    registration_service: RegistrationService,
    registration_repositories: tuple[AsyncMock, AsyncMock, AsyncMock],
    registration_identity: StartRegistration,
) -> None:
    # Arrange
    identity_repository = registration_repositories[0]
    identity_repository.get_registration_draft.return_value = None
    command = AdvanceRegistration(
        draft_id=99,
        provider=registration_identity.provider,
        external_user_id=registration_identity.external_user_id,
        step=RegistrationStep.CHURCH,
        answers={"church_id": 1},
    )

    # Act / Assert
    with pytest.raises(RegistrationDraftNotFoundError):
        await registration_service.advance(command)


async def test_registration_step_must_match_draft_state(
    registration_service: RegistrationService,
    registration_repositories: tuple[AsyncMock, AsyncMock, AsyncMock],
    registration_identity: StartRegistration,
    registration_draft: RegistrationDraft,
) -> None:
    # Arrange
    identity_repository = registration_repositories[0]
    registration_draft.current_step = RegistrationStep.NAME
    identity_repository.get_registration_draft.return_value = registration_draft
    command = AdvanceRegistration(
        draft_id=registration_draft.id,
        provider=registration_identity.provider,
        external_user_id=registration_identity.external_user_id,
        step=RegistrationStep.CHURCH,
        answers={"church_id": 1},
    )

    # Act / Assert
    with pytest.raises(RegistrationStepError, match="Expected step name"):
        await registration_service.advance(command)


async def test_church_step_saves_selected_church(
    registration_service: RegistrationService,
    registration_repositories: tuple[AsyncMock, AsyncMock, AsyncMock],
    registration_identity: StartRegistration,
    registration_draft: RegistrationDraft,
) -> None:
    # Arrange
    identity_repository = registration_repositories[0]
    church_repository = registration_repositories[2]
    church_repository.exists.return_value = True
    identity_repository.get_registration_draft.return_value = registration_draft
    updated_draft = replace(
        registration_draft,
        current_step=RegistrationStep.NAME,
        registration_data={"church_id": 7},
    )
    identity_repository.save_registration_step.return_value = updated_draft
    command = AdvanceRegistration(
        draft_id=registration_draft.id,
        provider=registration_identity.provider,
        external_user_id=registration_identity.external_user_id,
        step=RegistrationStep.CHURCH,
        answers={"church_id": 7},
    )

    # Act
    result = await registration_service.advance(command)

    # Assert
    assert_that(result.current_step, equal_to(RegistrationStep.NAME))
    identity_repository.save_registration_step.assert_awaited_once_with(
        registration_draft,
        RegistrationStep.NAME,
        {"church_id": 7},
    )


async def test_birthday_step_requires_dd_mm_yyyy(
    registration_service: RegistrationService,
    registration_repositories: tuple[AsyncMock, AsyncMock, AsyncMock],
    registration_identity: StartRegistration,
    registration_draft: RegistrationDraft,
) -> None:
    # Arrange
    identity_repository = registration_repositories[0]
    registration_draft.current_step = RegistrationStep.BIRTHDAY
    registration_draft.registration_data = {"church_id": 1, "name": "Анна", "surname": "Иванова"}
    identity_repository.get_registration_draft.return_value = registration_draft
    command = AdvanceRegistration(
        draft_id=registration_draft.id,
        provider=registration_identity.provider,
        external_user_id=registration_identity.external_user_id,
        step=RegistrationStep.BIRTHDAY,
        answers={"birthday": "2004-07-24"},
    )

    # Act / Assert
    with pytest.raises(RegistrationStepError, match="DD.MM.YYYY"):
        await registration_service.advance(command)


async def test_ministries_step_creates_global_catalog_entry_and_attaches_to_church(
    registration_service: RegistrationService,
    registration_repositories: tuple[AsyncMock, AsyncMock, AsyncMock],
    registration_identity: StartRegistration,
    registration_draft: RegistrationDraft,
) -> None:
    # Arrange
    identity_repository = registration_repositories[0]
    ministry_repository = registration_repositories[1]
    registration_draft.current_step = RegistrationStep.MINISTRIES
    registration_draft.registration_data = {"church_id": 1}
    identity_repository.get_registration_draft.return_value = registration_draft
    ministry_repository.get_catalog_type_by_name.return_value = None
    ministry_repository.create_catalog_type.return_value = MinistryType(
        5, "worship", "Прославление"
    )
    ministry_repository.add_to_church.return_value = ChurchMinistry(
        7, 1, 5, "worship", "Прославление"
    )
    command = AdvanceRegistration(
        draft_id=registration_draft.id,
        provider=registration_identity.provider,
        external_user_id=registration_identity.external_user_id,
        step=RegistrationStep.MINISTRIES,
        answers={"ministries": ["Прославление"]},
    )

    # Act
    await registration_service.advance(command)

    # Assert
    ministry_repository.create_catalog_type.assert_awaited_once_with("Прославление", None)
    ministry_repository.add_to_church.assert_awaited_once_with(1, 5)


async def test_consent_step_requires_explicit_acceptance(
    registration_service: RegistrationService,
    registration_repositories: tuple[AsyncMock, AsyncMock, AsyncMock],
    registration_identity: StartRegistration,
    registration_draft: RegistrationDraft,
) -> None:
    # Arrange
    identity_repository = registration_repositories[0]
    registration_draft.current_step = RegistrationStep.CONSENT
    identity_repository.get_registration_draft.return_value = registration_draft
    command = AdvanceRegistration(
        draft_id=registration_draft.id,
        provider=registration_identity.provider,
        external_user_id=registration_identity.external_user_id,
        step=RegistrationStep.CONSENT,
        answers={"accepted": False},
    )

    # Act / Assert
    with pytest.raises(ConsentRequiredError):
        await registration_service.advance(command)

    # Assert
    identity_repository.save_registration_step.assert_not_awaited()


async def test_review_requires_completed_registration_steps(
    registration_service: RegistrationService,
    registration_repositories: tuple[AsyncMock, AsyncMock, AsyncMock],
    registration_identity: StartRegistration,
    registration_draft: RegistrationDraft,
) -> None:
    # Arrange
    identity_repository = registration_repositories[0]
    registration_draft.current_step = RegistrationStep.CONSENT
    identity_repository.get_registration_draft.return_value = registration_draft

    # Act / Assert
    with pytest.raises(RegistrationStepError, match="not ready for review"):
        await registration_service.review(
            registration_draft.id,
            registration_identity.provider,
            registration_identity.external_user_id,
        )


async def test_confirm_requires_current_consent_version(
    registration_service: RegistrationService,
    registration_repositories: tuple[AsyncMock, AsyncMock, AsyncMock],
    registration_identity: StartRegistration,
    registration_draft: RegistrationDraft,
) -> None:
    # Arrange
    identity_repository = registration_repositories[0]
    registration_draft.current_step = RegistrationStep.REVIEW
    registration_draft.registration_data = {"consent_policy_version": "old-policy"}
    identity_repository.get_registration_draft.return_value = registration_draft

    # Act / Assert
    with pytest.raises(ConsentRequiredError, match="current policy version"):
        await registration_service.confirm(
            registration_draft.id,
            registration_identity.provider,
            registration_identity.external_user_id,
        )

    # Assert
    identity_repository.complete_registration.assert_not_awaited()


async def test_legacy_registration_cannot_create_unknown_roles(
    registration_service: RegistrationService,
    registration_repositories: tuple[AsyncMock, AsyncMock, AsyncMock],
    registration_identity: StartRegistration,
    registration_draft: RegistrationDraft,
) -> None:
    # Arrange
    identity = registration_repositories[0]
    ministries = registration_repositories[1]
    draft = replace(
        registration_draft,
        current_step=RegistrationStep.ROLES,
        registration_data={"ministries": [{"church_ministry_id": 1}]},
    )
    identity.get_registration_draft.return_value = draft
    ministries.get_role_by_name.return_value = None
    command = AdvanceRegistration(
        draft_id=draft.id,
        provider=registration_identity.provider,
        external_user_id=registration_identity.external_user_id,
        step=RegistrationStep.ROLES,
        answers={"roles": [{"church_ministry_id": 1, "role_names": ["администратоо"]}]},
    )

    # Act / Assert
    with pytest.raises(RegistrationStepError, match="справочника"):
        await registration_service.advance(command)
    ministries.create_role.assert_not_awaited()
    identity.save_registration_step.assert_not_awaited()
