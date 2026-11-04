import logging
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from bot_service.clients import backend, telegram
from bot_service.config import BotSettings
from bot_service.keyboards import add_web_link, menu_keyboard

logger = logging.getLogger(__name__)


async def handle_message(
    client: httpx.AsyncClient, settings: BotSettings, message: dict[str, Any]
) -> None:
    if message.get("chat", {}).get("type") != "private" or message.get("from", {}).get("is_bot"):
        return
    text = str(message.get("text", ""))
    if not text.strip():
        return
    identity = {"provider": "telegram", "external_user_id": str(message["from"]["id"])}
    markup = menu_keyboard(settings.web_url)
    try:
        invitation_command = re.fullmatch(r"/(accept|decline)_([0-9]+)", text.strip())
        if text.startswith("/start link_"):
            code = text.split(maxsplit=1)[1].removeprefix("link_")
            result = await backend(
                client,
                settings,
                "POST",
                "/internal/bot/link",
                {**identity, "code": code, "username": message["from"].get("username")},
            )
            reply = (
                "Telegram привязан к вашему аккаунту. "
                "Теперь здесь доступны расписание и напоминания."
            )
            reply += add_web_link(markup, "Личный кабинет", result["url"])
        elif invitation_command:
            accept = invitation_command.group(1) == "accept"
            await backend(
                client,
                settings,
                "POST",
                "/internal/bot/invitations/respond",
                {**identity, "invitation_id": int(invitation_command.group(2)), "accept": accept},
            )
            reply = "Участие подтверждено" if accept else "Отказ от приглашения сохранён"
        elif text.split()[0] in {"/login", "/web", "/plan"}:
            if text.startswith("/plan"):
                profile = await backend(client, settings, "POST", "/internal/bot/profile", identity)
                if not any(
                    "use_assistant" in ministry["permissions"] for ministry in profile["ministries"]
                ):
                    raise ValueError("Помощник доступен администратору служения")
            result = await backend(client, settings, "POST", "/internal/bot/login", identity)
            reply = "Вход в личный кабинет — кнопкой ниже. Ссылка действует 5 минут."
            reply += add_web_link(markup, "Войти на сайт", result["url"])
        elif text.split()[0] in {"/profile", "/schedule"}:
            result = await backend(client, settings, "POST", "/internal/bot/profile", identity)
            reply = (
                result["name"]
                + " "
                + result["surname"]
                + "\n"
                + "\n".join(
                    dict.fromkeys(
                        item["church_name"] + " · " + item["name"] for item in result["ministries"]
                    )
                )
            )
            if text.startswith("/schedule"):
                events = await backend(client, settings, "POST", "/internal/bot/schedule", identity)
                if not events:
                    reply += "\nВ ближайшие 30 дней событий нет."
                for event in events[:10]:
                    starts = datetime.fromisoformat(event["starts_at"]).astimezone(
                        ZoneInfo("Europe/Saratov")
                    )
                    reply += f"\n{starts:%d.%m %H:%M} — {event['event_name']}"
                link = await backend(client, settings, "POST", "/internal/bot/login", identity)
                reply += add_web_link(markup, "Открыть расписание", link["url"])
        elif text.split()[0] in {"/start", "/help"}:
            reply = (
                "Помощник служения Wolsar Worship\n\n"
                "Здесь можно смотреть расписание, получать напоминания и отвечать на приглашения. "
                "Выберите действие кнопкой ниже.\n\n"
                "Впервые здесь? Зарегистрируйтесь на сайте, затем откройте "
                "«Моя карточка → Привязать Telegram»."
            )
            try:
                profile = await backend(client, settings, "POST", "/internal/bot/profile", identity)
                if any(
                    "use_assistant" in ministry["permissions"] for ministry in profile["ministries"]
                ):
                    markup = menu_keyboard(settings.web_url, administrator=True)
            except httpx.HTTPStatusError:
                pass
        else:
            reply = (
                "Регистрация проходит на сайте: "
                + settings.web_url.rstrip("/")
                + "\nПосле входа откройте «Моя карточка → Привязать Telegram». "
                "Если аккаунт уже есть, повторная регистрация не нужна."
            )
    except ValueError as error:
        logger.warning("bot.command_rejected", extra={"error_type": type(error).__name__})
        reply = str(error)
    except httpx.HTTPStatusError as error:
        logger.warning("bot.command_failed", extra={"status_code": error.response.status_code})
        reply = (
            "Не удалось выполнить команду. Повторите позже или откройте личную карточку на сайте."
        )
        if error.response.status_code in {400, 404, 409, 422}:
            detail = error.response.json().get("detail")
            if isinstance(detail, str):
                reply = detail
    await telegram(
        client,
        settings,
        "sendMessage",
        {
            "chat_id": message["chat"]["id"],
            "text": reply[:4000],
            "disable_web_page_preview": True,
            "reply_markup": markup,
        },
    )
