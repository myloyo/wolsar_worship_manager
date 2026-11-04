import logging
import re
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx

from bot_service.config import BotSettings
from bot_service.observability import request_id_context

logger = logging.getLogger(__name__)


async def backend(
    client: httpx.AsyncClient,
    settings: BotSettings,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    started = perf_counter()
    route = re.sub(r"/[0-9]+(?=/|$)", "/{id}", path)
    metadata: dict[str, object] = {"provider": "backend", "method": method, "route": route}
    try:
        response = await client.request(
            method,
            settings.backend_url + path,
            headers={
                "Authorization": "Bearer " + settings.bot_service_token.get_secret_value(),
                "X-Request-ID": request_id_context.get() or uuid4().hex,
            },
            json=payload,
        )
        metadata["status_code"] = response.status_code
        response.raise_for_status()
        result = response.json() if response.content else None
    except Exception as error:
        metadata.update(
            error_type=type(error).__name__, duration_ms=round((perf_counter() - started) * 1000, 2)
        )
        logger.warning("backend.request_failed", extra=metadata)
        raise
    metadata["duration_ms"] = round((perf_counter() - started) * 1000, 2)
    logger.log(
        logging.DEBUG if path == "/internal/notifications/claim" else logging.INFO,
        "backend.request_completed",
        extra=metadata,
    )
    return result


async def telegram(
    client: httpx.AsyncClient, settings: BotSettings, method: str, payload: dict[str, Any]
) -> Any:
    started = perf_counter()
    metadata: dict[str, object] = {"provider": "telegram", "operation": method}
    try:
        response = await client.post(
            "https://api.telegram.org/bot"
            + settings.telegram_bot_token.get_secret_value()
            + "/"
            + method,
            json=payload,
        )
        metadata["status_code"] = response.status_code
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError("Telegram request failed")
        result = data["result"]
    except Exception as error:
        metadata.update(
            error_type=type(error).__name__, duration_ms=round((perf_counter() - started) * 1000, 2)
        )
        logger.warning("telegram.request_failed", extra=metadata)
        raise
    metadata["duration_ms"] = round((perf_counter() - started) * 1000, 2)
    logger.log(
        logging.DEBUG if method == "getUpdates" else logging.INFO,
        "telegram.request_completed",
        extra=metadata,
    )
    return result
