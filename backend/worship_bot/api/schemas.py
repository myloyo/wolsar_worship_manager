from datetime import date, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from worship_bot.domain.enums import (
    ConfirmationStatus,
    IdentityProvider,
    InvitationStatus,
    RegistrationStep,
    WorshipRole,
)


class ParticipantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    surname: str = Field(min_length=1, max_length=100)
    church_id: int = Field(gt=0)
    birthday_date: date | None = None
    consent_approved: bool
    worship_roles: list[WorshipRole] = Field(default_factory=list)


class ParticipantRead(BaseModel):
    id: int
    name: str
    surname: str
    church_id: int | None
    birthday_date: date | None
    consent_approved: bool
    worship_roles: list[WorshipRole]

    model_config = ConfigDict(from_attributes=True)


class EventTypeRead(BaseModel):
    id: int
    code: str
    custom_name: str | None
    is_default: bool


class ChurchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)

    model_config = ConfigDict(str_strip_whitespace=True)


class ChurchRead(BaseModel):
    id: int
    name: str


class EventCreate(BaseModel):
    event_name: str = Field(min_length=1, max_length=150)
    event_date: datetime
    event_type_id: int = Field(gt=0)
    church_id: int = Field(gt=0)


class EventRead(BaseModel):
    id: int
    event_name: str
    event_date: datetime
    event_type_id: int | None
    church_id: int | None


class AssignmentCreate(BaseModel):
    user_id: int = Field(gt=0)
    worship_role: WorshipRole


class AssignmentRead(BaseModel):
    id: int
    event_id: int
    user_id: int
    worship_role: WorshipRole
    confirmation_status: ConfirmationStatus


class EventRoleSlotCreate(BaseModel):
    ministry_role_id: int = Field(gt=0)
    slot_number: int = Field(default=1, ge=1)
    user_ministry_role_id: int | None = Field(default=None, gt=0)


class EventRoleSlotAssign(BaseModel):
    user_ministry_role_id: int = Field(gt=0)


class EventRoleSlotRead(BaseModel):
    id: int
    event_id: int
    ministry_role_id: int
    slot_number: int
    user_ministry_role_id: int | None
    confirmation_status: ConfirmationStatus


class EventSeriesCreate(BaseModel):
    event_name: str = Field(min_length=1, max_length=150)
    event_kind: Literal["sunday", "praise", "prayer", "leaders", "other"] | None = None
    starts_at: datetime
    timezone: str = "Europe/Saratov"
    recurrence_rule: str | None = Field(default=None, max_length=500)
    repeats_until: datetime | None = None
    additional_info: str | None = None
    song_ids: list[int] = Field(default_factory=list)
    role_slots: list[EventRoleSlotCreate] = Field(default_factory=list)

    rehearsal_at: AwareDatetime | None = None
    reminders_enabled: bool = False

    @model_validator(mode="after")
    def validate_rehearsal(self) -> "EventSeriesCreate":
        self.event_name = self.event_name.strip()
        if not self.event_name:
            raise ValueError("Укажите название события")
        if self.rehearsal_at is not None:
            if self.starts_at.tzinfo is None or self.rehearsal_at > self.starts_at:
                raise ValueError("Репетиция должна начинаться до события")
        return self


class EventCalendarItemRead(BaseModel):
    event_id: int
    event_name: str
    event_kind: str = "other"
    songs_text: str = ""
    clothing_text: str = ""
    content_revision: int = 0
    starts_at: datetime
    church_id: int
    church_ministry_id: int
    event_series_id: int | None
    additional_info: str | None
    song_ids: list[int]
    rehearsal_at: datetime | None = None
    event_reminder_at: datetime | None = None
    rehearsal_reminder_at: datetime | None = None
    role_slots: list[EventRoleSlotRead]


class RegistrationStart(BaseModel):
    provider: IdentityProvider
    external_user_id: str = Field(min_length=1, max_length=128)
    external_username: str | None = Field(default=None, max_length=150)


class RegistrationStepSubmit(BaseModel):
    provider: IdentityProvider
    external_user_id: str = Field(min_length=1, max_length=128)
    step: RegistrationStep
    answers: dict[str, object]


class RegistrationReviewRequest(BaseModel):
    provider: IdentityProvider
    external_user_id: str = Field(min_length=1, max_length=128)


class RegistrationDraftRead(BaseModel):
    id: int
    current_step: RegistrationStep
    registration_data: dict[str, object]


class RegistrationCompleteRead(BaseModel):
    user_id: int
    access_token: str
    token_type: str = "bearer"


class MinistryTypeRead(BaseModel):
    id: int
    code: str
    name: str


class ChurchMinistryRead(BaseModel):
    id: int
    church_id: int
    ministry_type_id: int
    ministry_type_code: str
    ministry_type_name: str


class MinistryAttachCreate(BaseModel):
    ministry_type_id: int = Field(gt=0)


class MinistryRoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    model_config = ConfigDict(str_strip_whitespace=True)


class MinistryRoleRead(BaseModel):
    id: int
    church_ministry_id: int
    code: str
    name: str


class RoleSelection(BaseModel):
    ministry_role_id: int = Field(gt=0)


class InvitationCreate(BaseModel):
    user_ministry_role_ids: list[int] = Field(min_length=1)


class InvitationResponse(BaseModel):
    accept: bool


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_id: int
    user_ministry_role_id: int
    status: InvitationStatus
    responded_at: AwareDatetime | None


class ScheduleReplace(BaseModel):
    rehearsal_at: AwareDatetime | None = None
    event_reminder_at: AwareDatetime | None = None
    rehearsal_reminder_at: AwareDatetime | None = None


class ScheduleRead(ScheduleReplace):
    id: int
    model_config = ConfigDict(from_attributes=True)


class SongsReplace(BaseModel):
    song_ids: list[int]
    comment: str | None = Field(default=None, max_length=2000)


class SongVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_id: int
    version_number: int
    edited_by_user_id: int | None
    comment: str | None
    created_at: AwareDatetime
    song_ids: list[int]


class LoginExchange(BaseModel):
    code: str = Field(min_length=20, max_length=100)


class BotIdentity(BaseModel):
    provider: IdentityProvider
    external_user_id: str = Field(min_length=1, max_length=128)


class LoginLinkRead(BaseModel):
    code: str
    url: str
    expires_at: datetime


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    surname: str = Field(min_length=1, max_length=100)
    birthday_date: date | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class AccessUpdate(BaseModel):
    access_level: str


class NotificationResult(BaseModel):
    claim_token: str
    delivered: bool


class NotificationRead(BaseModel):
    assignment_slot_id: int | None = None
    assignment_revision: str | None = None
    invitation_id: int | None = None
    id: int
    claim_token: str
    external_user_id: str
    text: str


class AssistantCreate(BaseModel):
    ministry_id: int = Field(gt=0)
    month: str = Field(pattern=r"^20[0-9]{2}-(0[1-9]|1[0-2])$")


class AssistantChat(BaseModel):
    message: str = Field(min_length=1, max_length=6000)


class ApplyProposal(BaseModel):
    revision: int = Field(ge=1)


class AssistantRead(BaseModel):
    id: str
    month: str
    messages: list[dict[str, object]]
    proposal: dict[str, object] | None
    revision: int
    attachment_count: int


class PortalAssignment(BaseModel):
    user_ministry_role_id: int | None = Field(default=None, gt=0)


class BotInvitationReply(BotIdentity):
    invitation_id: int = Field(gt=0)
    accept: bool


class PortalEventParticipant(PortalAssignment):
    ministry_role_id: int = Field(gt=0)


class MemberRoleCreate(BaseModel):
    ministry_role_id: int = Field(gt=0)
