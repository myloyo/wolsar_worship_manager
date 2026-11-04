from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from worship_bot.infrastructure.models import (
    EventNotificationPreferenceRecord,
    EventRecord,
    EventRoleSlotRecord,
    MinistryMembershipRecord,
    NotificationJobRecord,
    UserMinistryRoleRecord,
)


def notification_allowed_clause() -> ColumnElement[bool]:
    muted = exists().where(
        EventNotificationPreferenceRecord.event_id == NotificationJobRecord.event_id,
        EventNotificationPreferenceRecord.user_id == NotificationJobRecord.user_id,
        EventNotificationPreferenceRecord.enabled.is_(False),
    )
    return or_(NotificationJobRecord.notification_type == "replacement", ~muted)


async def event_recipients(session: AsyncSession, event_id: int) -> set[int]:
    assigned = await session.scalars(
        select(MinistryMembershipRecord.user_id)
        .join(
            UserMinistryRoleRecord,
            UserMinistryRoleRecord.ministry_membership_id == MinistryMembershipRecord.id,
        )
        .join(
            EventRoleSlotRecord,
            EventRoleSlotRecord.user_ministry_role_id == UserMinistryRoleRecord.id,
        )
        .where(EventRoleSlotRecord.event_id == event_id)
    )
    recipients = set(assigned)
    preferences = await session.scalars(
        select(EventNotificationPreferenceRecord)
        .join(EventRecord, EventRecord.id == EventNotificationPreferenceRecord.event_id)
        .join(
            MinistryMembershipRecord,
            (MinistryMembershipRecord.user_id == EventNotificationPreferenceRecord.user_id)
            & (MinistryMembershipRecord.church_ministry_id == EventRecord.church_ministry_id),
        )
        .where(EventNotificationPreferenceRecord.event_id == event_id)
    )
    for preference in preferences:
        if preference.enabled:
            recipients.add(preference.user_id)
        else:
            recipients.discard(preference.user_id)
    return recipients


async def event_notification_enabled(session: AsyncSession, job: NotificationJobRecord) -> bool:
    if job.notification_type == "replacement":
        return True
    preference = await session.get(EventNotificationPreferenceRecord, (job.event_id, job.user_id))
    return preference is None or preference.enabled
