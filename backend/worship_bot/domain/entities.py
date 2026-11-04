from dataclasses import dataclass
from datetime import date, datetime

from worship_bot.domain.enums import (
    ConfirmationStatus,
    IdentityProvider,
    InvitationStatus,
    NotificationStatus,
    RegistrationStep,
    WorshipRole,
)


@dataclass
class Participant:
    id: int
    name: str
    surname: str
    church_id: int | None
    birthday_date: date | None
    consent_approved: bool
    worship_roles: tuple[WorshipRole, ...]


@dataclass
class Event:
    id: int
    event_name: str
    event_date: datetime
    event_type_id: int | None
    church_id: int | None
    church_ministry_id: int | None = None
    event_series_id: int | None = None
    additional_info: str | None = None
    rehearsal_at: datetime | None = None
    event_reminder_at: datetime | None = None
    rehearsal_reminder_at: datetime | None = None
    event_kind: str = "other"
    songs_text: str = ""
    clothing_text: str = ""
    content_revision: int = 0


@dataclass
class Church:
    id: int
    name: str


@dataclass
class MinistryType:
    id: int
    code: str
    name: str
    created_by_user_id: int | None = None


@dataclass
class ChurchMinistry:
    id: int
    church_id: int
    ministry_type_id: int
    ministry_type_code: str
    ministry_type_name: str = ""


@dataclass
class MinistryRoleDefinition:
    id: int
    church_ministry_id: int
    code: str
    name: str
    created_by_user_id: int | None


@dataclass
class RegistrationDraft:
    id: int
    provider: IdentityProvider
    external_user_id: str
    external_username: str | None
    current_step: RegistrationStep
    status: str
    registration_data: dict[str, object]


@dataclass
class MinistryRole:
    id: int
    church_ministry_id: int
    code: str
    name: str


@dataclass
class EventSeries:
    id: int
    church_ministry_id: int
    event_name: str
    starts_at: datetime
    timezone: str
    recurrence_rule: str | None
    repeats_until: datetime | None


@dataclass
class EventRoleSlot:
    id: int
    event_id: int
    ministry_role_id: int
    slot_number: int
    user_ministry_role_id: int | None
    confirmation_status: ConfirmationStatus


@dataclass
class EventCalendarItem:
    event: Event
    role_slots: tuple[EventRoleSlot, ...]
    song_ids: tuple[int, ...]


@dataclass
class EventInvitation:
    id: int
    event_id: int
    user_ministry_role_id: int
    status: InvitationStatus
    responded_at: datetime | None


@dataclass
class EventSongSetVersion:
    id: int
    event_id: int
    version_number: int
    edited_by_user_id: int | None
    comment: str | None
    created_at: datetime
    song_ids: tuple[int, ...]


@dataclass
class NotificationJob:
    id: int
    event_id: int
    user_id: int
    notification_type: str
    scheduled_at: datetime
    status: NotificationStatus


@dataclass
class EventType:
    id: int
    code: str
    custom_name: str | None
    is_default: bool


@dataclass
class EventAssignment:
    id: int
    event_id: int
    user_id: int
    worship_role: WorshipRole
    confirmation_status: ConfirmationStatus
