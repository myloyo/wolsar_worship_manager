import asyncio
import logging
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx

from bot_service.clients import backend, telegram
from bot_service.config import BotSettings
from bot_service.keyboards import assignment_keyboard, invitation_keyboard, menu_keyboard
from bot_service.observability import request_id_context

logger = logging.getLogger(__name__)


async def deliver_job(
    client: httpx.AsyncClient, settings: BotSettings, job: dict[str, Any]
) -> None:
    token = request_id_context.set(uuid4().hex)
    started = perf_counter()
    delivered = False
    try:
        try:
            await telegram(
                client,
                settings,
                "sendMessage",
                {
                    "chat_id": job["external_user_id"],
                    "text": job["text"][:4000],
                    "reply_markup": assignment_keyboard(
                        job["assignment_slot_id"], job["assignment_revision"]
                    )
                    if job.get("assignment_slot_id") and job.get("assignment_revision")
                    else invitation_keyboard(job["invitation_id"])
                    if job.get("invitation_id")
                    else menu_keyboard(settings.web_url),
                },
            )
            delivered = True
        except (httpx.HTTPError, RuntimeError) as error:
            logger.warning(
                "notification.delivery_failed",
                extra={"job_id": job["id"], "error_type": type(error).__name__},
            )
        await backend(
            client,
            settings,
            "POST",
            f"/internal/notifications/{job['id']}/result",
            {"claim_token": job["claim_token"], "delivered": delivered},
        )
        logger.info(
            "notification.delivery_completed",
            extra={
                "job_id": job["id"],
                "outcome": "sent" if delivered else "retry",
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
    finally:
        request_id_context.reset(token)


async def deliver_notifications(settings: BotSettings) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            try:
                jobs = await backend(client, settings, "POST", "/internal/notifications/claim")
                if jobs:
                    logger.info("notification.batch_claimed", extra={"count": len(jobs)})
                for job in jobs:
                    await deliver_job(client, settings, job)
            except (httpx.HTTPError, RuntimeError) as error:
                logger.warning(
                    "notification.worker_retry", extra={"error_type": type(error).__name__}
                )
            await asyncio.sleep(15)
