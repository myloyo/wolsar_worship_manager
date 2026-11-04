import asyncio
import logging

from bot_service.config import BotSettings
from bot_service.observability import configure_logging
from bot_service.workers.notifications import deliver_notifications
from bot_service.workers.polling import poll_messages


async def main() -> None:
    configure_logging("bot")
    logger = logging.getLogger(__name__)
    settings = BotSettings()
    if (
        not settings.telegram_bot_token.get_secret_value()
        or not settings.bot_service_token.get_secret_value()
    ):
        raise RuntimeError("Configure TELEGRAM_BOT_TOKEN and BOT_SERVICE_TOKEN")
    logger.info("service.started")
    try:
        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(poll_messages(settings))
            tasks.create_task(deliver_notifications(settings))
    except Exception:
        logger.exception("service.failed")
        raise SystemExit(1) from None
    finally:
        logger.info("service.stopped")


if __name__ == "__main__":
    asyncio.run(main())
