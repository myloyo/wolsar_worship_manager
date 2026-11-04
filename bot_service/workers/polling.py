import asyncio
import logging
from pathlib import Path

import httpx

from bot_service.clients import telegram
from bot_service.config import BotSettings
from bot_service.handlers.updates import handle_update

logger = logging.getLogger(__name__)


async def poll_messages(settings: BotSettings) -> None:
    offset_path = Path(settings.offset_file)
    offset_path.parent.mkdir(parents=True, exist_ok=True)
    offset = int(offset_path.read_text()) if offset_path.exists() else 0
    async with httpx.AsyncClient(timeout=40) as client:
        connected = False
        while True:
            try:
                updates = await telegram(
                    client,
                    settings,
                    "getUpdates",
                    {
                        "offset": offset,
                        "timeout": 25,
                        "allowed_updates": ["message", "callback_query"],
                    },
                )
                if not connected:
                    logger.info("bot.polling_connected")
                    connected = True
                for update in updates:
                    await handle_update(client, settings, update)
                    offset = update["update_id"] + 1
                    offset_path.write_text(str(offset))
            except (httpx.HTTPError, RuntimeError) as error:
                status = (
                    error.response.status_code
                    if isinstance(error, httpx.HTTPStatusError)
                    else "network"
                )
                logger.warning(
                    "bot.polling_retry",
                    extra={"status_code": status, "error_type": type(error).__name__},
                )
                await asyncio.sleep(5)
