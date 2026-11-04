from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from worship_bot.application.exceptions import (
    EventInvitationNotFoundError,
    EventInvitationStateError,
    EventNotFoundError,
)
from worship_bot.domain.entities import Event, EventInvitation, EventRoleSlot, EventSongSetVersion
from worship_bot.domain.enums import ConfirmationStatus, InvitationStatus, NotificationStatus
from worship_bot.infrastructure.models import (
    EventInvitationRecord,
    EventRecord,
    EventRoleSlotRecord,
    EventSongRecord,
    EventSongSetVersionItemRecord,
    EventSongSetVersionRecord,
    MinistryMembershipRecord,
    NotificationJobRecord,
    SongRecord,
    UserMinistryRoleRecord,
)
from worship_bot.infrastructure.notification_queue import queue_event_reminders


class SqlEventLifecycleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_role_for_event(
        self,
        event_id: int,
        user_id: int,
        ministry_role_id: int,
    ) -> int | None:
        role_id = await self.session.scalar(
            select(UserMinistryRoleRecord.id)
            .join(
                MinistryMembershipRecord,
                MinistryMembershipRecord.id == UserMinistryRoleRecord.ministry_membership_id,
            )
            .join(
                EventRecord,
                EventRecord.church_ministry_id == MinistryMembershipRecord.church_ministry_id,
            )
            .where(
                EventRecord.id == event_id,
                MinistryMembershipRecord.user_id == user_id,
                UserMinistryRoleRecord.ministry_role_id == ministry_role_id,
            )
        )
        return int(role_id) if role_id is not None else None

    async def user_role_is_for_event(
        self,
        event_id: int,
        user_ministry_role_id: int,
    ) -> bool:
        found = await self.session.scalar(
            select(UserMinistryRoleRecord.id)
            .join(
                MinistryMembershipRecord,
                MinistryMembershipRecord.id == UserMinistryRoleRecord.ministry_membership_id,
            )
            .join(
                EventRecord,
                EventRecord.church_ministry_id == MinistryMembershipRecord.church_ministry_id,
            )
            .where(
                EventRecord.id == event_id,
                UserMinistryRoleRecord.id == user_ministry_role_id,
            )
        )
        return found is not None

    async def self_signup(
        self,
        event_id: int,
        user_id: int,
        user_ministry_role_id: int,
    ) -> EventRoleSlot:
        from worship_bot.infrastructure.repositories.event_preferences import require_role_eligible

        target_event = await self.session.get(EventRecord, event_id)
        if target_event is not None:
            await require_role_eligible(
                self.session, user_ministry_role_id, target_event.event_kind
            )
        await self.session.scalar(
            select(EventRecord).where(EventRecord.id == event_id).with_for_update()
        )
        role_id = await self.session.scalar(
            select(UserMinistryRoleRecord.ministry_role_id)
            .join(
                MinistryMembershipRecord,
                MinistryMembershipRecord.id == UserMinistryRoleRecord.ministry_membership_id,
            )
            .where(
                UserMinistryRoleRecord.id == user_ministry_role_id,
                MinistryMembershipRecord.user_id == user_id,
            )
        )
        if role_id is None:
            raise EventInvitationNotFoundError(user_ministry_role_id)

        slot = await self.session.scalar(
            select(EventRoleSlotRecord).where(
                EventRoleSlotRecord.event_id == event_id,
                EventRoleSlotRecord.user_ministry_role_id == user_ministry_role_id,
            )
        )
        if slot is None:
            slot = await self.session.scalar(
                select(EventRoleSlotRecord)
                .where(
                    EventRoleSlotRecord.event_id == event_id,
                    EventRoleSlotRecord.ministry_role_id == role_id,
                    EventRoleSlotRecord.user_ministry_role_id.is_(None),
                )
                .order_by(EventRoleSlotRecord.slot_number)
                .with_for_update()
            )
        if slot is None:
            max_slot = await self.session.scalar(
                select(func.max(EventRoleSlotRecord.slot_number)).where(
                    EventRoleSlotRecord.event_id == event_id,
                    EventRoleSlotRecord.ministry_role_id == role_id,
                )
            )
            slot = EventRoleSlotRecord(
                event_id=event_id,
                ministry_role_id=role_id,
                slot_number=(max_slot or 0) + 1,
            )
            self.session.add(slot)

        slot.user_ministry_role_id = user_ministry_role_id
        slot.confirmation_status = ConfirmationStatus.CONFIRMED.value
        invitation = await self.session.scalar(
            select(EventInvitationRecord).where(
                EventInvitationRecord.event_id == event_id,
                EventInvitationRecord.user_ministry_role_id == user_ministry_role_id,
            )
        )
        if invitation is not None:
            invitation.status = InvitationStatus.ACCEPTED.value
            invitation.responded_at = datetime.now(UTC)
        await self.session.flush()
        await queue_event_reminders(self.session, event_id)
        await self.session.commit()
        await self.session.refresh(slot)
        return self.map_slot(slot)

    async def self_withdraw(
        self,
        event_id: int,
        user_id: int,
        ministry_role_id: int,
    ) -> bool:
        role_membership_id = await self.get_user_role_for_event(event_id, user_id, ministry_role_id)
        if role_membership_id is None:
            return False
        slot = await self.session.scalar(
            select(EventRoleSlotRecord).where(
                EventRoleSlotRecord.event_id == event_id,
                EventRoleSlotRecord.user_ministry_role_id == role_membership_id,
            )
        )
        if slot is None:
            return False
        slot.user_ministry_role_id = None
        slot.confirmation_status = ConfirmationStatus.PENDING.value
        invitation = await self.session.scalar(
            select(EventInvitationRecord).where(
                EventInvitationRecord.event_id == event_id,
                EventInvitationRecord.user_ministry_role_id == role_membership_id,
            )
        )
        if invitation is not None:
            invitation.status = InvitationStatus.DECLINED.value
            invitation.responded_at = datetime.now(UTC)
        remaining_assignment = await self.session.scalar(
            select(EventRoleSlotRecord.id)
            .join(
                UserMinistryRoleRecord,
                UserMinistryRoleRecord.id == EventRoleSlotRecord.user_ministry_role_id,
            )
            .join(
                MinistryMembershipRecord,
                MinistryMembershipRecord.id == UserMinistryRoleRecord.ministry_membership_id,
            )
            .where(
                EventRoleSlotRecord.event_id == event_id,
                MinistryMembershipRecord.user_id == user_id,
            )
        )
        if remaining_assignment is None:
            await self.session.execute(
                update(NotificationJobRecord)
                .where(
                    NotificationJobRecord.event_id == event_id,
                    NotificationJobRecord.user_id == user_id,
                    NotificationJobRecord.notification_type.in_(
                        ("event", "rehearsal", "event_2h", "rehearsal_2h")
                    ),
                    NotificationJobRecord.status == NotificationStatus.PENDING.value,
                )
                .values(status=NotificationStatus.CANCELLED.value)
            )
        await self.session.commit()
        return True

    async def invite_candidates(
        self,
        event_id: int,
        invited_by_user_id: int,
        user_ministry_role_ids: tuple[int, ...],
    ) -> list[EventInvitation]:
        invitations: list[EventInvitation] = []
        for user_role_id in user_ministry_role_ids:
            existing = await self.session.scalar(
                select(EventInvitationRecord).where(
                    EventInvitationRecord.event_id == event_id,
                    EventInvitationRecord.user_ministry_role_id == user_role_id,
                )
            )
            if existing is None:
                existing = EventInvitationRecord(
                    event_id=event_id,
                    user_ministry_role_id=user_role_id,
                    invited_by_user_id=invited_by_user_id,
                    status=InvitationStatus.INVITED.value,
                )
                self.session.add(existing)
                await self.session.flush()
                user_id = await self.session.scalar(
                    select(MinistryMembershipRecord.user_id)
                    .join(
                        UserMinistryRoleRecord,
                        UserMinistryRoleRecord.ministry_membership_id
                        == MinistryMembershipRecord.id,
                    )
                    .where(UserMinistryRoleRecord.id == user_role_id)
                )
                if user_id is not None:
                    now = datetime.now(UTC)
                    self.session.add(
                        NotificationJobRecord(
                            event_id=event_id,
                            user_id=user_id,
                            notification_type="invitation",
                            scheduled_at=now,
                            payload={"invitation_id": existing.id},
                            deduplication_key=f"invite:{event_id}:{user_role_id}",
                        )
                    )
            invitations.append(self.map_invitation(existing))
        await self.session.commit()
        return invitations

    async def list_invitations(self, event_id: int) -> list[EventInvitation]:
        records = await self.session.scalars(
            select(EventInvitationRecord)
            .where(EventInvitationRecord.event_id == event_id)
            .order_by(EventInvitationRecord.created_at)
        )
        return [self.map_invitation(record) for record in records]

    async def respond_to_invitation(
        self,
        invitation_id: int,
        user_id: int,
        accept: bool,
    ) -> EventInvitation:
        invitation = await self.session.scalar(
            select(EventInvitationRecord)
            .join(
                UserMinistryRoleRecord,
                UserMinistryRoleRecord.id == EventInvitationRecord.user_ministry_role_id,
            )
            .join(
                MinistryMembershipRecord,
                MinistryMembershipRecord.id == UserMinistryRoleRecord.ministry_membership_id,
            )
            .where(
                EventInvitationRecord.id == invitation_id,
                MinistryMembershipRecord.user_id == user_id,
            )
            .with_for_update()
        )
        if invitation is None:
            raise EventInvitationNotFoundError(invitation_id)
        new_status = InvitationStatus.ACCEPTED if accept else InvitationStatus.DECLINED
        if invitation.status != InvitationStatus.INVITED.value:
            if invitation.status == new_status.value:
                return self.map_invitation(invitation)
            raise EventInvitationStateError("Invitation has already been answered")
        invitation.status = new_status.value
        invitation.responded_at = datetime.now(UTC)
        await self.session.execute(
            update(NotificationJobRecord)
            .where(
                NotificationJobRecord.event_id == invitation.event_id,
                NotificationJobRecord.notification_type == "invitation",
                NotificationJobRecord.deduplication_key
                == f"invite:{invitation.event_id}:{invitation.user_ministry_role_id}",
                NotificationJobRecord.status == NotificationStatus.PENDING.value,
            )
            .values(status=NotificationStatus.CANCELLED.value)
        )
        if accept:
            await self.self_signup(invitation.event_id, user_id, invitation.user_ministry_role_id)
        else:
            await self.session.commit()
        await self.session.refresh(invitation)
        return self.map_invitation(invitation)

    async def set_event_schedule(
        self,
        event_id: int,
        rehearsal_at: datetime | None,
        event_reminder_at: datetime | None,
        rehearsal_reminder_at: datetime | None,
    ) -> Event:
        event = await self.session.scalar(
            select(EventRecord).where(EventRecord.id == event_id).with_for_update()
        )
        if event is None:
            raise EventNotFoundError(event_id)
        event.rehearsal_at = rehearsal_at
        event.event_reminder_at = event_reminder_at
        event.rehearsal_reminder_at = rehearsal_reminder_at
        await self.session.flush()
        await queue_event_reminders(self.session, event_id)
        await self.session.commit()
        await self.session.refresh(event)
        return self.map_event(event)

    async def get_event_context(self, event_id: int) -> tuple[int, str] | None:
        from worship_bot.infrastructure.models import ChurchMinistryRecord, MinistryTypeRecord

        result = await self.session.execute(
            select(ChurchMinistryRecord.id, MinistryTypeRecord.code)
            .join(
                MinistryTypeRecord, MinistryTypeRecord.id == ChurchMinistryRecord.ministry_type_id
            )
            .join(EventRecord, EventRecord.church_ministry_id == ChurchMinistryRecord.id)
            .where(EventRecord.id == event_id)
        )
        row = result.one_or_none()
        return (row.id, row.code) if row is not None else None

    async def get_event(self, event_id: int) -> Event | None:
        record = await self.session.get(EventRecord, event_id)
        return self.map_event(record) if record is not None else None

    async def replace_song_set(
        self,
        event_id: int,
        user_id: int,
        song_ids: tuple[int, ...],
        comment: str | None,
    ) -> EventSongSetVersion:
        from worship_bot.infrastructure.repositories.event_preferences import (
            SqlEventPreferencesRepository,
        )

        if not await SqlEventPreferencesRepository(self.session).can_edit_content(
            event_id, user_id
        ):
            from worship_bot.application.exceptions import AccessDeniedError

            raise AccessDeniedError("Список песен меняет только назначенный ведущий вокалист")
        event = await self.session.scalar(
            select(EventRecord).where(EventRecord.id == event_id).with_for_update()
        )
        if event is None:
            raise EventNotFoundError(event_id)
        current_version = await self.session.scalar(
            select(func.max(EventSongSetVersionRecord.version_number)).where(
                EventSongSetVersionRecord.event_id == event_id
            )
        )
        version = EventSongSetVersionRecord(
            event_id=event_id,
            version_number=(current_version or 0) + 1,
            edited_by_user_id=user_id,
            comment=comment,
        )
        self.session.add(version)
        await self.session.flush()
        self.session.add_all(
            [
                EventSongSetVersionItemRecord(
                    version_id=version.id,
                    song_id=song_id,
                    position=position,
                )
                for position, song_id in enumerate(song_ids)
            ]
        )
        await self.session.execute(
            delete(EventSongRecord).where(EventSongRecord.event_id == event_id)
        )
        self.session.add_all(
            [
                EventSongRecord(event_id=event_id, song_id=song_id, position=position)
                for position, song_id in enumerate(song_ids)
            ]
        )
        from worship_bot.infrastructure.notification_queue import queue_content_update

        await queue_content_update(self.session, event)
        await self.session.commit()
        return EventSongSetVersion(
            version.id,
            event_id,
            version.version_number,
            user_id,
            comment,
            version.created_at,
            song_ids,
        )

    async def list_song_set_versions(self, event_id: int) -> list[EventSongSetVersion]:
        versions = await self.session.scalars(
            select(EventSongSetVersionRecord)
            .where(EventSongSetVersionRecord.event_id == event_id)
            .order_by(EventSongSetVersionRecord.version_number)
        )
        result: list[EventSongSetVersion] = []
        for version in versions:
            song_ids = await self.session.scalars(
                select(EventSongSetVersionItemRecord.song_id)
                .where(EventSongSetVersionItemRecord.version_id == version.id)
                .order_by(EventSongSetVersionItemRecord.position)
            )
            result.append(
                EventSongSetVersion(
                    version.id,
                    event_id,
                    version.version_number,
                    version.edited_by_user_id,
                    version.comment,
                    version.created_at,
                    tuple(song_ids),
                )
            )
        return result

    async def song_ids_exist(self, song_ids: tuple[int, ...]) -> bool:
        if not song_ids:
            return True
        count = await self.session.scalar(
            select(func.count(func.distinct(SongRecord.id))).where(SongRecord.id.in_(song_ids))
        )
        return count == len(set(song_ids))

    @staticmethod
    def map_event(record: EventRecord) -> Event:
        return Event(
            id=record.id,
            event_name=record.event_name,
            event_date=record.event_date,
            event_type_id=record.event_type_id,
            church_id=record.church_id,
            church_ministry_id=record.church_ministry_id,
            event_series_id=record.event_series_id,
            additional_info=record.additional_info,
            rehearsal_at=record.rehearsal_at,
            event_reminder_at=record.event_reminder_at,
            rehearsal_reminder_at=record.rehearsal_reminder_at,
        )

    @staticmethod
    def map_invitation(record: EventInvitationRecord) -> EventInvitation:
        return EventInvitation(
            record.id,
            record.event_id,
            record.user_ministry_role_id,
            InvitationStatus(record.status),
            record.responded_at,
        )

    @staticmethod
    def map_slot(record: EventRoleSlotRecord) -> EventRoleSlot:
        return EventRoleSlot(
            record.id,
            record.event_id,
            record.ministry_role_id,
            record.slot_number,
            record.user_ministry_role_id,
            ConfirmationStatus(record.confirmation_status),
        )
