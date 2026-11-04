from dataclasses import replace
from datetime import UTC, datetime
from itertools import islice
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.rrule import rrulestr

from worship_bot.application.commands import (
    AssignEventRoleSlot,
    EditEventSongs,
    EventInvitationRequest,
    EventRoleSlotRequest,
    NewAssignment,
    NewEvent,
    NewEventRoleSlot,
    NewEventSeries,
    SetEventSchedule,
)
from worship_bot.application.exceptions import (
    AccessDeniedError,
    ChurchMinistryNotFoundError,
    ChurchNotFoundError,
    EventNotFoundError,
    EventRoleSlotNotFoundError,
    EventSeriesValidationError,
    EventSongsNotAllowedError,
    EventTypeNotFoundError,
    InvalidRecurrenceRuleError,
    MinistryRoleNotFoundError,
    ParticipantNotFoundError,
    RoleAssignmentMismatchError,
    UserMinistryRoleNotFoundError,
)
from worship_bot.application.repositories import (
    ChurchRepository,
    EventCalendarRepository,
    EventLifecycleRepository,
    MinistryRepository,
    ScheduleRepository,
)
from worship_bot.domain.entities import (
    Event,
    EventAssignment,
    EventCalendarItem,
    EventInvitation,
    EventRoleSlot,
    EventSongSetVersion,
    EventType,
)
from worship_bot.domain.enums import ConfirmationStatus


class ScheduleService:
    def __init__(
        self,
        repository: ScheduleRepository,
        church_repository: ChurchRepository,
    ) -> None:
        self.repository = repository
        self.church_repository = church_repository

    async def event_types(self) -> list[EventType]:
        return await self.repository.list_event_types()

    async def create_event(self, event: NewEvent) -> Event:
        if await self.repository.get_event_type(event.event_type_id) is None:
            raise EventTypeNotFoundError(event.event_type_id)
        if not await self.church_repository.exists(event.church_id):
            raise ChurchNotFoundError(event.church_id)
        return await self.repository.create_event(event)

    async def events(self, start: datetime | None, end: datetime | None) -> list[Event]:
        if start is not None and end is not None and start > end:
            raise ValueError("start must be earlier than or equal to end")
        return await self.repository.list_events(start, end)

    async def assign(
        self,
        assignment: NewAssignment,
        status: ConfirmationStatus = ConfirmationStatus.PENDING,
    ) -> EventAssignment:
        if not await self.repository.event_exists(assignment.event_id):
            raise EventNotFoundError(assignment.event_id)
        if not await self.repository.participant_exists(assignment.user_id):
            raise ParticipantNotFoundError(assignment.user_id)
        return await self.repository.add_assignment(assignment, status)


class EventCalendarService:
    maximum_occurrences = 100

    def __init__(self, repository: EventCalendarRepository) -> None:
        self.repository = repository

    async def create_series(self, series: NewEventSeries) -> list[EventCalendarItem]:
        ministry = await self.repository.get_church_ministry(series.church_ministry_id)
        if ministry is None:
            raise ChurchMinistryNotFoundError(series.church_ministry_id)
        if series.rehearsal_offset_minutes is not None and series.rehearsal_offset_minutes < 0:
            raise EventSeriesValidationError("Репетиция должна начинаться до события")
        series = replace(
            series,
            role_slots=await self.complete_role_slots(series.church_ministry_id, series.role_slots),
        )
        await self.validate_role_slots(series.church_ministry_id, series.role_slots)
        if series.song_ids:
            if ministry.ministry_type_code != "worship":
                raise EventSongsNotAllowedError("Songs can only be attached to worship events")
            if len(set(series.song_ids)) != len(series.song_ids):
                raise EventSeriesValidationError("Song IDs must be unique")
            if not await self.repository.song_ids_exist(series.song_ids):
                raise EventSeriesValidationError("A selected song does not exist")
        occurrence_dates = self.expand_occurrences(series)
        if any(occurrence <= datetime.now(UTC) for occurrence in occurrence_dates):
            raise EventSeriesValidationError("Дата и время события должны быть в будущем")
        return await self.repository.create_event_series(series, occurrence_dates)

    async def complete_role_slots(
        self, ministry_id: int, slots: tuple[EventRoleSlotRequest, ...]
    ) -> tuple[EventRoleSlotRequest, ...]:
        result = list(slots)
        defaults = await self.repository.default_role_slots(ministry_id)
        for default in defaults:
            matching = [
                slot for slot in result if slot.ministry_role_id == default.ministry_role_id
            ]
            required = sum(slot.ministry_role_id == default.ministry_role_id for slot in defaults)
            if len(matching) < required:
                result.append(
                    EventRoleSlotRequest(
                        default.ministry_role_id,
                        max((slot.slot_number for slot in matching), default=0) + 1,
                    )
                )
        return tuple(result)

    async def validate_role_slots(
        self, church_ministry_id: int, role_slots: tuple[EventRoleSlotRequest, ...]
    ) -> None:
        role_slot_keys = tuple((slot.ministry_role_id, slot.slot_number) for slot in role_slots)
        role_ids = tuple(slot.ministry_role_id for slot in role_slots)
        if len(set(role_slot_keys)) != len(role_slot_keys):
            raise EventSeriesValidationError("Role slot numbers must be unique per role")
        if any(slot.slot_number < 1 for slot in role_slots):
            raise EventSeriesValidationError("slot_number must be positive")
        if not await self.repository.ministry_role_ids_belong_to(church_ministry_id, role_ids):
            raise MinistryRoleNotFoundError("A role does not belong to this ministry")
        user_role_ids = tuple(
            slot.user_ministry_role_id
            for slot in role_slots
            if slot.user_ministry_role_id is not None
        )
        if not await self.repository.user_role_ids_belong_to(church_ministry_id, user_role_ids):
            raise UserMinistryRoleNotFoundError(
                "A selected participant does not have this ministry role"
            )
        for slot in role_slots:
            if (
                slot.user_ministry_role_id is not None
                and not await self.repository.user_ministry_role_matches(
                    slot.user_ministry_role_id, slot.ministry_role_id
                )
            ):
                raise RoleAssignmentMismatchError(
                    "Selected participant role does not match the slot"
                )

    async def list_events(
        self,
        start: datetime,
        end: datetime,
        church_ministry_id: int | None = None,
    ) -> list[EventCalendarItem]:
        if start > end:
            raise ValueError("start must be earlier than or equal to end")
        return await self.repository.list_calendar_events(start, end, church_ministry_id)

    async def add_role_slot(self, slot: NewEventRoleSlot) -> EventRoleSlot:
        ministry_id = await self.repository.get_event_ministry_id(slot.event_id)
        if ministry_id is None:
            raise EventRoleSlotNotFoundError(slot.event_id)
        if not await self.repository.ministry_role_ids_belong_to(
            ministry_id, (slot.ministry_role_id,)
        ):
            raise MinistryRoleNotFoundError(slot.ministry_role_id)
        if (
            slot.user_ministry_role_id is not None
            and not await self.repository.user_role_ids_belong_to(
                ministry_id, (slot.user_ministry_role_id,)
            )
        ):
            raise UserMinistryRoleNotFoundError(slot.user_ministry_role_id)
        if (
            slot.user_ministry_role_id is not None
            and not await self.repository.user_ministry_role_matches(
                slot.user_ministry_role_id, slot.ministry_role_id
            )
        ):
            raise RoleAssignmentMismatchError("Selected participant role does not match the slot")
        if slot.slot_number < 1:
            raise EventSeriesValidationError("slot_number must be positive")
        return await self.repository.add_role_slot(slot)

    async def assign_role_slot(self, assignment: AssignEventRoleSlot) -> EventRoleSlot:
        ministry_id = await self.repository.get_event_role_slot_ministry_id(
            assignment.event_role_slot_id
        )
        if ministry_id is None:
            raise EventRoleSlotNotFoundError(assignment.event_role_slot_id)
        slot_context = await self.repository.get_event_role_slot_context(
            assignment.event_role_slot_id
        )
        if slot_context is None:
            raise EventRoleSlotNotFoundError(assignment.event_role_slot_id)
        if not await self.repository.user_role_ids_belong_to(
            ministry_id, (assignment.user_ministry_role_id,)
        ):
            raise UserMinistryRoleNotFoundError(assignment.user_ministry_role_id)
        if not await self.repository.user_ministry_role_matches(
            assignment.user_ministry_role_id, slot_context[1]
        ):
            raise RoleAssignmentMismatchError("Selected participant role does not match the slot")
        return await self.repository.assign_role_slot(assignment)

    def expand_occurrences(self, series: NewEventSeries) -> tuple[datetime, ...]:
        if series.starts_at.tzinfo is None or series.starts_at.utcoffset() is None:
            raise InvalidRecurrenceRuleError("starts_at must include a timezone")
        try:
            timezone = ZoneInfo(series.timezone)
        except (ValueError, ZoneInfoNotFoundError) as error:
            raise InvalidRecurrenceRuleError("timezone must be a valid IANA timezone") from error
        start = series.starts_at.astimezone(timezone)
        if series.recurrence_rule is None:
            return (start,)
        if series.repeats_until is None and not any(
            token.startswith(("COUNT=", "UNTIL="))
            for token in series.recurrence_rule.upper().removeprefix("RRULE:").split(";")
        ):
            raise InvalidRecurrenceRuleError(
                "recurrence_rule must have COUNT or UNTIL, or repeats_until must be set"
            )
        try:
            rule = rrulestr(series.recurrence_rule, dtstart=start)
            if series.repeats_until is not None and (
                series.repeats_until.tzinfo is None or series.repeats_until.utcoffset() is None
            ):
                raise InvalidRecurrenceRuleError("repeats_until must include a timezone")
            until = (
                series.repeats_until.astimezone(timezone)
                if series.repeats_until is not None
                else None
            )
            dates: list[datetime] = []
            for occurrence in islice(
                rule.xafter(start, count=self.maximum_occurrences + 1, inc=True),
                self.maximum_occurrences + 1,
            ):
                if until is not None and occurrence > until:
                    break
                dates.append(occurrence)
        except (TypeError, ValueError) as error:
            if isinstance(error, InvalidRecurrenceRuleError):
                raise
            raise InvalidRecurrenceRuleError(
                "recurrence_rule is not a valid RFC 5545 RRULE"
            ) from error
        if not dates:
            raise InvalidRecurrenceRuleError("recurrence_rule must generate at least one date")
        if len(dates) > self.maximum_occurrences:
            raise InvalidRecurrenceRuleError(
                f"A series cannot generate more than {self.maximum_occurrences} occurrences"
            )
        return tuple(dates)


class EventLifecycleService:
    manager_access_levels = {"coordinator", "admin", "developer"}

    def __init__(
        self,
        repository: EventLifecycleRepository,
        ministry_repository: MinistryRepository,
    ) -> None:
        self.repository = repository
        self.ministry_repository = ministry_repository

    async def self_signup(
        self,
        event_id: int,
        user_id: int,
        ministry_role_id: int,
    ) -> EventRoleSlot:
        context = await self.repository.get_event_context(event_id)
        if context is None:
            raise EventNotFoundError(event_id)
        user_role_id = await self.repository.get_user_role_for_event(
            event_id, user_id, ministry_role_id
        )
        if user_role_id is None:
            raise UserMinistryRoleNotFoundError(ministry_role_id)
        return await self.repository.self_signup(event_id, user_id, user_role_id)

    async def self_withdraw(
        self,
        event_id: int,
        user_id: int,
        ministry_role_id: int,
    ) -> None:
        context = await self.repository.get_event_context(event_id)
        if context is None:
            raise EventNotFoundError(event_id)
        user_role_id = await self.repository.get_user_role_for_event(
            event_id, user_id, ministry_role_id
        )
        if user_role_id is None:
            raise UserMinistryRoleNotFoundError(ministry_role_id)
        if not await self.repository.self_withdraw(event_id, user_id, ministry_role_id):
            raise EventRoleSlotNotFoundError("No self-assignment exists for this event and role")

    async def invite(
        self,
        event_id: int,
        actor_user_id: int,
        requests: tuple[EventInvitationRequest, ...],
    ) -> list[EventInvitation]:
        context = await self.repository.get_event_context(event_id)
        if context is None:
            raise EventNotFoundError(event_id)
        church_ministry_id = context[0]
        await self.require_manager(actor_user_id, church_ministry_id)
        if not requests:
            raise EventSeriesValidationError("At least one invite candidate is required")
        candidate_ids = tuple(request.user_ministry_role_id for request in requests)
        if len(set(candidate_ids)) != len(candidate_ids):
            raise EventSeriesValidationError("Invite candidates must be unique")
        for request in requests:
            if not await self.repository.user_role_is_for_event(
                event_id, request.user_ministry_role_id
            ):
                raise UserMinistryRoleNotFoundError(request.user_ministry_role_id)
        return await self.repository.invite_candidates(event_id, actor_user_id, candidate_ids)

    async def invitations(self, event_id: int, actor_user_id: int) -> list[EventInvitation]:
        context = await self.repository.get_event_context(event_id)
        if context is None:
            raise EventNotFoundError(event_id)
        await self.require_manager(actor_user_id, context[0])
        return await self.repository.list_invitations(event_id)

    async def respond_to_invitation(
        self,
        invitation_id: int,
        user_id: int,
        accept: bool,
    ) -> EventInvitation:
        return await self.repository.respond_to_invitation(invitation_id, user_id, accept)

    async def set_schedule(
        self,
        schedule: SetEventSchedule,
        actor_user_id: int,
    ) -> Event:
        context = await self.repository.get_event_context(schedule.event_id)
        if context is None:
            raise EventNotFoundError(schedule.event_id)
        await self.require_manager(actor_user_id, context[0])
        event = await self.repository.get_event(schedule.event_id)
        if event is None:
            raise EventNotFoundError(schedule.event_id)
        for value in (
            schedule.rehearsal_at,
            schedule.event_reminder_at,
            schedule.rehearsal_reminder_at,
        ):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise EventSeriesValidationError("Schedule times must include a timezone")
        if schedule.rehearsal_at is not None and schedule.rehearsal_at >= event.event_date:
            raise EventSeriesValidationError("Rehearsal must be before the event")
        if (
            schedule.event_reminder_at is not None
            and schedule.event_reminder_at >= event.event_date
        ):
            raise EventSeriesValidationError("Event reminder must be before the event")
        if schedule.rehearsal_reminder_at is not None:
            if schedule.rehearsal_at is None:
                raise EventSeriesValidationError("Set rehearsal time before its reminder")
            if schedule.rehearsal_reminder_at >= schedule.rehearsal_at:
                raise EventSeriesValidationError("Rehearsal reminder must be before rehearsal")
        return await self.repository.set_event_schedule(
            schedule.event_id,
            schedule.rehearsal_at,
            schedule.event_reminder_at,
            schedule.rehearsal_reminder_at,
        )

    async def edit_song_set(
        self,
        edit: EditEventSongs,
        actor_user_id: int,
    ) -> EventSongSetVersion:
        context = await self.repository.get_event_context(edit.event_id)
        if context is None:
            raise EventNotFoundError(edit.event_id)
        church_ministry_id, ministry_type_code = context
        if ministry_type_code != "worship":
            raise EventSongsNotAllowedError("Songs can only be attached to worship events")
        can_edit = await self.ministry_repository.can_edit_song_set(
            actor_user_id, church_ministry_id
        )
        if not can_edit:
            raise AccessDeniedError("Only vocalists and ministry managers can edit the song list")
        if len(set(edit.song_ids)) != len(edit.song_ids):
            raise EventSeriesValidationError("Song IDs must be unique")
        if not await self.repository.song_ids_exist(edit.song_ids):
            raise EventSeriesValidationError("A selected song does not exist")
        return await self.repository.replace_song_set(
            edit.event_id, actor_user_id, edit.song_ids, edit.comment
        )

    async def song_history(
        self,
        event_id: int,
        actor_user_id: int,
    ) -> list[EventSongSetVersion]:
        context = await self.repository.get_event_context(event_id)
        if context is None:
            raise EventNotFoundError(event_id)
        access = await self.ministry_repository.access_level(actor_user_id, context[0])
        if access is None:
            raise AccessDeniedError("Ministry membership is required")
        return await self.repository.list_song_set_versions(event_id)

    async def require_manager(self, actor_user_id: int, church_ministry_id: int) -> None:
        access = await self.ministry_repository.access_level(actor_user_id, church_ministry_id)
        if access not in self.manager_access_levels:
            raise AccessDeniedError("Ministry manager permission is required")
