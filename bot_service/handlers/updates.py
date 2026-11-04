import logging
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx

from bot_service.config import BotSettings
from bot_service.handlers.callbacks import handle_callback
from bot_service.handlers.messages import handle_message
from bot_service.observability import request_id_context

logger = logging.getLogger(__name__)


async def handle_update(
    client: httpx.AsyncClient, settings: BotSettings, update: dict[str, Any]
) -> None:
    token = request_id_context.set(uuid4().hex)
    started = perf_counter()
    outcome = "handled"
    update_id = update.get("update_id")
    try:
        if "message" in update:
            await handle_message(client, settings, update["message"])
        elif "callback_query" in update:
            await handle_callback(client, settings, update["callback_query"])
        else:
            outcome = "ignored"
    except httpx.HTTPStatusError as error:
        outcome = "rejected"
        if error.response.status_code not in {400, 403, 404}:
            outcome = "failed"
            raise
        logger.warning(
            "bot.update_rejected",
            extra={"update_id": update_id, "status_code": error.response.status_code},
        )
    except Exception:
        outcome = "failed"
        logger.exception("bot.update_failed", extra={"update_id": update_id})
        raise
    finally:
        logger.info(
            "bot.update_completed",
            extra={
                "update_id": update_id,
                "outcome": outcome,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        request_id_context.reset(token)
