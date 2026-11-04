from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worship_bot.application.exceptions import AccessDeniedError, EventSeriesValidationError
from worship_bot.domain.event_kinds import role_allows_event
from worship_bot.infrastructure.models import (
    EventRecord,
    EventRoleSlotRecord,
    MinistryMembershipRecord,
    MinistryRoleRecord,
    UserMinistryRoleRecord,
)
from worship_bot.infrastructure.notification_queue import queue_content_update


async def require_role_eligible(session: AsyncSession, role_id: int, event_kind: str) -> None:
    role = await session.scalar(
        select(UserMinistryRoleRecord).where(UserMinistryRoleRecord.id == role_id).with_for_update()
    )
    if role is None or not role_allows_event(role.allowed_event_kinds, event_kind):
        raise EventSeriesValidationError(
            "Для этой роли участнику не разрешён выбранный вид собрания"
        )


class SqlEventPreferencesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def set_role_kinds(
        self, actor_id: int, ministry_id: int, user_id: int, role_id: int, kinds: list[str]
    ) -> None:
        from worship_bot.infrastructure.repositories.portal import SqlPortalRepository

        await SqlPortalRepository(self.session).require_permission(
            actor_id, ministry_id, "manage_assignments"
        )
        role = await self.session.scalar(
            select(UserMinistryRoleRecord)
            .join(
                MinistryMembershipRecord,
                MinistryMembershipRecord.id == UserMinistryRoleRecord.ministry_membership_id,
            )
            .where(
                UserMinistryRoleRecord.id == role_id,
                MinistryMembershipRecord.church_ministry_id == ministry_id,
                MinistryMembershipRecord.user_id == user_id,
            )
            .with_for_update(of=UserMinistryRoleRecord)
        )
        if role is None:
            raise LookupError("Роль участника не найдена в этой команде")
        events = await self.session.scalars(
            select(EventRecord)
            .join(EventRoleSlotRecord, EventRoleSlotRecord.event_id == EventRecord.id)
            .where(
                EventRoleSlotRecord.user_ministry_role_id == role_id,
                EventRecord.event_date >= datetime.now(UTC),
            )
        )
        for event in events:
            if not role_allows_event(kinds, event.event_kind):
                raise EventSeriesValidationError(
                    f"Сначала измените назначение на «{event.event_name}»: "
                    "оно противоречит ограничению"
                )
        role.allowed_event_kinds = sorted(set(kinds))
        await self.session.commit()

    async def can_edit_content(self, event_id: int, user_id: int) -> bool:
        role = await self.session.scalar(
            select(UserMinistryRoleRecord.id)
            .join(
                EventRoleSlotRecord,
                EventRoleSlotRecord.user_ministry_role_id == UserMinistryRoleRecord.id,
            )
            .join(
                MinistryMembershipRecord,
                MinistryMembershipRecord.id == UserMinistryRoleRecord.ministry_membership_id,
            )
            .join(
                MinistryRoleRecord, MinistryRoleRecord.id == UserMinistryRoleRecord.ministry_role_id
            )
            .where(
                EventRoleSlotRecord.event_id == event_id,
                MinistryMembershipRecord.user_id == user_id,
                MinistryRoleRecord.code == "lead_vocal",
            )
        )
        return role is not None

    async def save_content(
        self, event_id: int, user_id: int, revision: int, songs_text: str, clothing_text: str
    ) -> None:
        event = await self.session.scalar(
            select(EventRecord).where(EventRecord.id == event_id).with_for_update()
        )
        if event is None:
            raise LookupError("Событие не найдено")
        if not await self.can_edit_content(event_id, user_id):
            raise AccessDeniedError(
                "Список песен и одежду меняет только назначенный ведущий вокалист"
            )
        if event.content_revision != revision:
            raise EventSeriesValidationError("Информация уже изменена. Обновите событие")
        if event.songs_text == songs_text and event.clothing_text == clothing_text:
            return
        event.songs_text, event.clothing_text = songs_text, clothing_text
        await queue_content_update(self.session, event)
        await self.session.commit()

    async def set_event_kind(self, event_id: int, user_id: int, kind: str) -> None:
        from worship_bot.infrastructure.repositories.portal import SqlPortalRepository

        event = await self.session.scalar(
            select(EventRecord).where(EventRecord.id == event_id).with_for_update()
        )
        if event is None or event.church_ministry_id is None:
            raise LookupError("Событие не найдено")
        await SqlPortalRepository(self.session).require_permission(
            user_id, event.church_ministry_id, "manage_events"
        )
        roles = await self.session.scalars(
            select(EventRoleSlotRecord.user_ministry_role_id).where(
                EventRoleSlotRecord.event_id == event_id,
                EventRoleSlotRecord.user_ministry_role_id.is_not(None),
            )
        )
        for role_id in roles:
            if role_id is not None:
                await require_role_eligible(self.session, role_id, kind)
        event.event_kind = kind
        await self.session.commit()
