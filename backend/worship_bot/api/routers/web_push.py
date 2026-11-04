import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, update

from worship_bot.api.push_schemas import PushRegistration, PushState
from worship_bot.api.routers.portal import Configuration, CurrentUser, Session
from worship_bot.infrastructure.models.web_push import PushSubscriptionRecord
from worship_bot.infrastructure.push_sender import send_push, valid_push_endpoint

router = APIRouter(prefix="/portal/push", tags=["web notifications"])


@router.get("/config")
async def push_config(user_id: CurrentUser, settings: Configuration) -> dict[str, str | bool]:
    return {
        "available": bool(settings.vapid_private_key and settings.vapid_public_key),
        "public_key": settings.vapid_public_key,
    }


@router.post("/subscriptions", status_code=204)
async def subscribe(
    payload: PushRegistration, user_id: CurrentUser, session: Session, settings: Configuration
) -> None:
    if not settings.vapid_private_key or not settings.vapid_public_key:
        raise HTTPException(503, "Отправка уведомлений пока не настроена")
    if not valid_push_endpoint(payload.endpoint):
        raise HTTPException(422, "Этот сервис браузерных уведомлений пока не поддерживается")
    record = await session.scalar(
        select(PushSubscriptionRecord)
        .where(PushSubscriptionRecord.endpoint == payload.endpoint)
        .with_for_update()
    )
    if record is not None and record.user_id != user_id:
        raise HTTPException(
            409, "Подписка принадлежит другому аккаунту. Отключите её перед сменой аккаунта"
        )
    if record is None:
        record = PushSubscriptionRecord(
            user_id=user_id,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
        )
        session.add(record)
    record.enabled = True
    record.p256dh, record.auth = payload.keys.p256dh, payload.keys.auth
    record.checked_at = datetime.now(UTC)
    await session.commit()


@router.post("/state", status_code=204)
async def sync_push_state(payload: PushState, user_id: CurrentUser, session: Session) -> None:
    await session.execute(
        update(PushSubscriptionRecord)
        .where(
            PushSubscriptionRecord.user_id == user_id,
            PushSubscriptionRecord.endpoint == payload.endpoint,
        )
        .values(enabled=payload.permission == "granted", checked_at=datetime.now(UTC))
    )
    await session.commit()


@router.delete("/subscriptions", status_code=204)
async def unsubscribe(payload: PushState, user_id: CurrentUser, session: Session) -> None:
    await session.execute(
        update(PushSubscriptionRecord)
        .where(
            PushSubscriptionRecord.user_id == user_id,
            PushSubscriptionRecord.endpoint == payload.endpoint,
        )
        .values(enabled=False, checked_at=datetime.now(UTC))
    )
    await session.commit()


@router.post("/check", status_code=204)
async def check_push(
    payload: PushState, user_id: CurrentUser, session: Session, settings: Configuration
) -> None:
    record = await session.scalar(
        select(PushSubscriptionRecord).where(
            PushSubscriptionRecord.user_id == user_id,
            PushSubscriptionRecord.endpoint == payload.endpoint,
            PushSubscriptionRecord.enabled.is_(True),
        )
    )
    if record is None:
        raise HTTPException(409, "Сначала подключите уведомления на этом устройстве")
    result = await asyncio.to_thread(
        send_push,
        record.endpoint,
        record.p256dh,
        record.auth,
        {
            "title": "Уведомления подключены",
            "body": "Здесь будут напоминания о служениях и репетициях.",
            "url": "/profile",
            "tag": "push-check",
        },
        settings,
    )
    if result == "expired":
        record.enabled = False
        await session.commit()
    if result != "sent":
        raise HTTPException(503, "Не удалось отправить уведомление. Попробуйте подключить заново")
