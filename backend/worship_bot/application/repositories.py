from datetime import datetime
from typing import Protocol

from worship_bot.application.commands import (
    AssignEventRoleSlot,
    EventRoleSlotRequest,
    NewAssignment,
    NewChurch,
    NewEvent,
    NewEventRoleSlot,
    NewEventSeries,
    NewParticipant,
    RegistrationMinistry,
    StartRegistration,
)
from worship_bot.domain.entities import (
    Church,
    ChurchMinistry,
    Event,
    EventAssignment,
    EventCalendarItem,
    EventInvitation,
    EventRoleSlot,
    EventSongSetVersion,
    EventType,
    MinistryRoleDefinition,
    MinistryType,
    Participant,
    RegistrationDraft,
)
from worship_bot.domain.enums import ConfirmationStatus, IdentityProvider, RegistrationStep


class ParticipantRepository(Protocol):
    async def create(self, participant: NewParticipant) -> Participant: ...

    async def get_by_id(self, participant_id: int) -> Participant | None: ...


class ChurchRepository(Protocol):
    async def exists(self, church_id: int) -> bool: ...

    async def get_by_name(self, name: str) -> Church | None: ...

    async def create(self, church: NewChurch) -> Church: ...

    async def list_all(self) -> list[Church]: ...


class ScheduleRepository(Protocol):
    async def get_event_type(self, event_type_id: int) -> EventType | None: ...

    async def list_event_types(self) -> list[EventType]: ...

    async def create_event(self, event: NewEvent) -> Event: ...

    async def list_events(self, start: datetime | None, end: datetime | None) -> list[Event]: ...

    async def participant_exists(self, participant_id: int) -> bool: ...

    async def event_exists(self, event_id: int) -> bool: ...

    async def add_assignment(
        self,
        assignment: NewAssignment,
        status: ConfirmationStatus,
    ) -> EventAssignment: ...


class EventCalendarRepository(Protocol):
    async def default_role_slots(
        self, church_ministry_id: int
    ) -> tuple[EventRoleSlotRequest, ...]: ...

    async def get_church_ministry(self, church_ministry_id: int) -> ChurchMinistry | None: ...

    async def ministry_role_ids_belong_to(
        self,
        church_ministry_id: int,
        role_ids: tuple[int, ...],
    ) -> bool: ...

    async def user_role_ids_belong_to(
        self,
        church_ministry_id: int,
        user_role_ids: tuple[int, ...],
    ) -> bool: ...

    async def song_ids_exist(self, song_ids: tuple[int, ...]) -> bool: ...

    async def create_event_series(
        self,
        series: NewEventSeries,
        occurrence_dates: tuple[datetime, ...],
    ) -> list[EventCalendarItem]: ...

    async def list_calendar_events(
        self,
        start: datetime,
        end: datetime,
        church_ministry_id: int | None,
    ) -> list[EventCalendarItem]: ...

    async def get_event_ministry_id(self, event_id: int) -> int | None: ...

    async def get_event_role_slot_ministry_id(self, slot_id: int) -> int | None: ...

    async def get_event_role_slot_context(self, slot_id: int) -> tuple[int, int] | None: ...

    async def user_ministry_role_matches(
        self,
        user_ministry_role_id: int,
        ministry_role_id: int,
    ) -> bool: ...

    async def add_role_slot(self, slot: NewEventRoleSlot) -> EventRoleSlot: ...

    async def assign_role_slot(self, assignment: AssignEventRoleSlot) -> EventRoleSlot: ...


class EventLifecycleRepository(Protocol):
    async def get_event_context(self, event_id: int) -> tuple[int, str] | None: ...

    async def get_event(self, event_id: int) -> Event | None: ...

    async def get_user_role_for_event(
        self,
        event_id: int,
        user_id: int,
        ministry_role_id: int,
    ) -> int | None: ...

    async def user_role_is_for_event(
        self,
        event_id: int,
        user_ministry_role_id: int,
    ) -> bool: ...

    async def self_signup(
        self,
        event_id: int,
        user_id: int,
        user_ministry_role_id: int,
    ) -> EventRoleSlot: ...

    async def self_withdraw(
        self,
        event_id: int,
        user_id: int,
        ministry_role_id: int,
    ) -> bool: ...

    async def invite_candidates(
        self,
        event_id: int,
        invited_by_user_id: int,
        user_ministry_role_ids: tuple[int, ...],
    ) -> list[EventInvitation]: ...

    async def list_invitations(self, event_id: int) -> list[EventInvitation]: ...

    async def respond_to_invitation(
        self,
        invitation_id: int,
        user_id: int,
        accept: bool,
    ) -> EventInvitation: ...

    async def set_event_schedule(
        self,
        event_id: int,
        rehearsal_at: datetime | None,
        event_reminder_at: datetime | None,
        rehearsal_reminder_at: datetime | None,
    ) -> Event: ...

    async def replace_song_set(
        self,
        event_id: int,
        user_id: int,
        song_ids: tuple[int, ...],
        comment: str | None,
    ) -> EventSongSetVersion: ...

    async def list_song_set_versions(self, event_id: int) -> list[EventSongSetVersion]: ...

    async def song_ids_exist(self, song_ids: tuple[int, ...]) -> bool: ...


class IdentityRepository(Protocol):
    async def start_registration(self, command: StartRegistration) -> RegistrationDraft: ...

    async def external_account_exists(
        self,
        provider: IdentityProvider,
        external_user_id: str,
    ) -> bool: ...

    async def get_registration_draft(
        self,
        draft_id: int,
        provider: IdentityProvider,
        external_user_id: str,
    ) -> RegistrationDraft | None: ...

    async def save_registration_step(
        self,
        draft: RegistrationDraft,
        step: RegistrationStep,
        data: dict[str, object],
    ) -> RegistrationDraft: ...

    async def complete_registration(self, draft: RegistrationDraft) -> int: ...

    async def get_user_id_for_external_account(
        self,
        provider: IdentityProvider,
        external_user_id: str,
    ) -> int | None: ...


class MinistryRepository(Protocol):
    async def list_catalog(self) -> list[MinistryType]: ...

    async def list_church_ministries(self, church_id: int) -> list[ChurchMinistry]: ...

    async def get_church_ministry(self, church_ministry_id: int) -> ChurchMinistry | None: ...

    async def add_to_church(self, church_id: int, ministry_type_id: int) -> ChurchMinistry: ...

    async def church_ministry_exists(self, church_id: int, church_ministry_id: int) -> bool: ...

    async def church_access_level(self, user_id: int, church_id: int) -> str | None: ...

    async def get_catalog_type_by_name(self, name: str) -> MinistryType | None: ...

    async def create_catalog_type(
        self, name: str, created_by_user_id: int | None
    ) -> MinistryType: ...

    async def list_roles(self, church_ministry_id: int) -> list[MinistryRoleDefinition]: ...

    async def get_role_by_name(
        self,
        church_ministry_id: int,
        name: str,
    ) -> MinistryRoleDefinition | None: ...

    async def create_role(
        self,
        church_ministry_id: int,
        name: str,
        created_by_user_id: int | None,
    ) -> MinistryRoleDefinition: ...

    async def add_user_memberships(
        self,
        user_id: int,
        church_id: int,
        ministries: tuple[RegistrationMinistry, ...],
    ) -> None: ...

    async def access_level(self, user_id: int, church_ministry_id: int) -> str | None: ...

    async def add_user_role(
        self,
        user_id: int,
        church_ministry_id: int,
        ministry_role_id: int,
    ) -> None: ...

    async def set_access_level(
        self,
        user_id: int,
        church_ministry_id: int,
        access_level: str,
    ) -> bool: ...

    async def can_edit_song_set(self, user_id: int, church_ministry_id: int) -> bool: ...
