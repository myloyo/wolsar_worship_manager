import asyncio
import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from worship_bot.config import get_settings
from worship_bot.infrastructure.database import engine, session_factory
from worship_bot.infrastructure.event_notifications import (
    event_notification_enabled,
    notification_allowed_clause,
)
from worship_bot.infrastructure.models import NotificationJobRecord
from worship_bot.infrastructure.models.web_push import PushDeliveryRecord, PushSubscriptionRecord
from worship_bot.infrastructure.push_sender import send_push
from worship_bot.observability import configure_logging

logger = logging.getLogger(__name__)


def job_fingerprint(job: NotificationJobRecord) -> str:
    value = json.dumps(
        {"payload": job.payload, "scheduled_at": job.scheduled_at.isoformat()}, sort_keys=True
    )
    return hashlib.sha256(value.encode()).hexdigest()


async def deliver_pending() -> None:
    settings = get_settings()
    if not settings.vapid_private_key or not settings.vapid_public_key:
        return
    now = datetime.now(UTC)
    async with session_factory() as session:
        subscriptions = list(
            await session.scalars(
                select(PushSubscriptionRecord)
                .where(PushSubscriptionRecord.enabled.is_(True))
                .with_for_update(skip_locked=True)
            )
        )
        for subscription in subscriptions:
            jobs = list(
                await session.scalars(
                    select(NotificationJobRecord)
                    .where(
                        NotificationJobRecord.user_id == subscription.user_id,
                        notification_allowed_clause(),
                        NotificationJobRecord.status != "cancelled",
                        NotificationJobRecord.scheduled_at <= now,
                        NotificationJobRecord.scheduled_at >= now - timedelta(days=1),
                        NotificationJobRecord.scheduled_at >= subscription.created_at,
                    )
                    .order_by(NotificationJobRecord.scheduled_at)
                    .limit(100)
                )
            )
            for job in jobs:
                if not await event_notification_enabled(session, job):
                    continue
                fingerprint = job_fingerprint(job)
                delivery = await session.scalar(
                    select(PushDeliveryRecord).where(
                        PushDeliveryRecord.subscription_id == subscription.id,
                        PushDeliveryRecord.job_id == job.id,
                        PushDeliveryRecord.fingerprint == fingerprint,
                    )
                )
                if delivery is None:
                    delivery = PushDeliveryRecord(
                        subscription_id=subscription.id,
                        job_id=job.id,
                        fingerprint=fingerprint,
                        attempts=0,
                    )
                    session.add(delivery)
                elif (
                    delivery.status == "sent"
                    or delivery.attempts >= 5
                    or delivery.retry_at.replace(tzinfo=UTC) > now
                ):
                    continue
                rehearsal = job.notification_type.startswith("rehearsal")
                result = await asyncio.to_thread(
                    send_push,
                    subscription.endpoint,
                    subscription.p256dh,
                    subscription.auth,
                    {
                        "title": "Репетиция" if rehearsal else "Ваше служение",
                        "body": str(
                            job.payload.get("text")
                            or job.payload.get("event_name")
                            or "Изменения в расписании"
                        ),
                        "url": "/schedule",
                        "tag": f"event-{job.event_id}-{job.notification_type}",
                    },
                    settings,
                )
                delivery.attempts += 1
                logger.log(
                    logging.INFO if result == "sent" else logging.WARNING,
                    "push.delivery_completed",
                    extra={
                        "job_id": job.id,
                        "event_id": job.event_id,
                        "outcome": result,
                        "attempt": delivery.attempts,
                    },
                )
                delivery.status = "sent" if result == "sent" else "pending"
                delivery.retry_at = now + timedelta(seconds=min(3600, 30 * 2**delivery.attempts))
                if result == "expired":
                    subscription.enabled = False
                    break
        await session.commit()


async def run() -> None:
    configure_logging("push-worker")
    logger.info("service.started")
    try:
        while True:
            try:
                await deliver_pending()
            except Exception:
                logger.exception("push.worker_retry")
            await asyncio.sleep(15)
    finally:
        logger.info("service.stopped")
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
