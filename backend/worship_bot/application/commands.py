from dataclasses import dataclass
from datetime import date, datetime

from worship_bot.domain.enums import IdentityProvider, RegistrationStep, WorshipRole


@dataclass
class NewParticipant:
    name: str
    surname: str
    church_id: int
    birthday_date: date | None
    consent_approved: bool
    worship_roles: tuple[WorshipRole, ...]


@dataclass
class NewEvent:
    event_name: str
    event_date: datetime
    event_type_id: int
    church_id: int


@dataclass
class NewChurch:
    name: str


@dataclass
class NewAssignment:
    event_id: int
    user_id: int
    worship_role: WorshipRole


@dataclass
class EventRoleSlotRequest:
    ministry_role_id: int
    slot_number: int = 1
    user_ministry_role_id: int | None = None


@dataclass
class NewEventSeries:
    church_ministry_id: int
    event_name: str
    starts_at: datetime
    timezone: str
    recurrence_rule: str | None
    repeats_until: datetime | None
    additional_info: str | None
    song_ids: tuple[int, ...]
    role_slots: tuple[EventRoleSlotRequest, ...]
    rehearsal_offset_minutes: int | None = None
    reminders_enabled: bool = False
    event_kind: str | None = None


@dataclass
class NewEventRoleSlot:
    event_id: int
    ministry_role_id: int
    slot_number: int = 1
    user_ministry_role_id: int | None = None


@dataclass
class AssignEventRoleSlot:
    event_role_slot_id: int
    user_ministry_role_id: int


@dataclass
class EventInvitationRequest:
    user_ministry_role_id: int


@dataclass
class RespondToEventInvitation:
    invitation_id: int
    accept: bool


@dataclass
class SetEventSchedule:
    event_id: int
    rehearsal_at: datetime | None
    event_reminder_at: datetime | None
    rehearsal_reminder_at: datetime | None


@dataclass
class EditEventSongs:
    event_id: int
    song_ids: tuple[int, ...]
    comment: str | None = None


@dataclass
class StartRegistration:
    provider: IdentityProvider
    external_user_id: str
    external_username: str | None


@dataclass
class AdvanceRegistration:
    draft_id: int
    provider: IdentityProvider
    external_user_id: str
    step: RegistrationStep
    answers: dict[str, object]


@dataclass
class RegistrationMinistry:
    church_ministry_id: int
    role_names: tuple[str, ...]
