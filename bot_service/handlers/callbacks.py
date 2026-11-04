import logging
import re
from typing import Any

import httpx

from bot_service.clients import backend, telegram
from bot_service.config import BotSettings
from bot_service.handlers.messages import handle_message
from bot_service.keyboards import menu_keyboard

logger = logging.getLogger(__name__)


async def handle_callback(
    client: httpx.AsyncClient, settings: BotSettings, callback: dict[str, Any]
) -> None:
    message = callback.get("message", {})
    if message.get("chat", {}).get("type") != "private" or callback.get("from", {}).get("is_bot"):
        return
    await telegram(client, settings, "answerCallbackQuery", {"callback_query_id": callback["id"]})
    identity = {"provider": "telegram", "external_user_id": str(callback["from"]["id"])}
    data = str(callback.get("data", ""))
    chat_id = message["chat"]["id"]
    markup = menu_keyboard(settings.web_url)
    try:
        if data == "website":
            reply = "Сайт: " + settings.web_url.rstrip("/")
        elif data.startswith("nav:"):
            command = data.removeprefix("nav:")
            if command not in {"schedule", "profile", "plan", "help"}:
                return
            await handle_message(
                client,
                settings,
                {
                    "chat": message["chat"],
                    "from": callback["from"],
                    "text": "/" + command,
                },
            )
            return
        elif re.fullmatch(r"assignment:(accept|decline):[0-9]+:[0-9]{20}", data):
            action, slot_id, revision = data.split(":")[1:]
            await backend(
                client,
                settings,
                "POST",
                "/internal/bot/assignments/respond",
                {
                    **identity,
                    "slot_id": int(slot_id),
                    "revision": revision,
                    "accept": action == "accept",
                },
            )
            reply = (
                "Участие подтверждено. Спасибо!"
                if action == "accept"
                else "Замена запрошена. Координатор и админы уведомлены. "
                "Вы остаётесь в составе до назначения замены."
            )
            await telegram(
                client,
                settings,
                "editMessageReplyMarkup",
                {
                    "chat_id": chat_id,
                    "message_id": message["message_id"],
                    "reply_markup": {"inline_keyboard": []},
                },
            )
        elif re.fullmatch(r"invite:(accept|decline):[0-9]+", data):
            action, invitation_id = data.split(":")[1:]
            await backend(
                client,
                settings,
                "POST",
                "/internal/bot/invitations/respond",
                {
                    **identity,
                    "invitation_id": int(invitation_id),
                    "accept": action == "accept",
                },
            )
            reply = (
                "Участие подтверждено. Спасибо!"
                if action == "accept"
                else "Вы отказались от приглашения."
            )
            await telegram(
                client,
                settings,
                "editMessageReplyMarkup",
                {
                    "chat_id": chat_id,
                    "message_id": message["message_id"],
                    "reply_markup": {"inline_keyboard": []},
                },
            )
        elif data == "teams" or re.fullmatch(r"(?:(?:team|apply):[0-9]+|role:[0-9]+:[0-9]+)", data):
            churches = await backend(client, settings, "POST", "/internal/bot/directory", identity)
            teams = [
                (church["name"], team)
                for church in churches
                for team in church["teams"]
                if team["status"] not in {"member", "pending"}
            ]
            if data == "teams":
                reply = (
                    "Выберите команду для заявки:"
                    if teams
                    else "Новых команд для заявки нет. Вы уже участник или ожидаете одобрения."
                )
                markup = {
                    "inline_keyboard": [
                        [
                            {
                                "text": f"{church} · {team['name']}",
                                "callback_data": f"team:{team['id']}",
                            }
                        ]
                        for church, team in teams[:40]
                    ]
                    + [[{"text": "Назад в меню", "callback_data": "nav:help"}]]
                }
            else:
                ministry_id = int(data.split(":")[1])
                match = next(
                    ((church, team) for church, team in teams if team["id"] == ministry_id), None
                )
                if match is None:
                    raise ValueError(
                        "Команда недоступна для новой заявки. Откройте список команд заново."
                    )
                church, team = match
                selected = set()
                for row in message.get("reply_markup", {}).get("inline_keyboard", []):
                    for button in row:
                        key = str(button.get("callback_data", ""))
                        if key.startswith(f"role:{ministry_id}:") and button["text"].startswith(
                            "✓ "
                        ):
                            selected.add(int(key.split(":")[2]))
                catalog = {role["id"]: role["name"] for role in team["roles"]}
                selected.intersection_update(catalog)
                if data.startswith("role:"):
                    role_id = int(data.split(":")[2])
                    if role_id not in catalog:
                        raise ValueError("Эта роль больше недоступна. Откройте список заново.")
                    selected.symmetric_difference_update({role_id})
                if len(selected) > 30:
                    raise ValueError("Можно выбрать до 30 ролей.")
                names = (
                    ", ".join(catalog[role_id] for role_id in sorted(selected))
                    or "Роли уточнит администратор"
                )
                if data.startswith("apply:"):
                    await backend(
                        client,
                        settings,
                        "POST",
                        "/internal/bot/applications",
                        {
                            **identity,
                            "church_ministry_id": ministry_id,
                            "role_ids": sorted(selected),
                        },
                    )
                    reply = f"""Заявка отправлена
{church} · {team["name"]}
Роли: {names}
Администратор команды рассмотрит её на сайте."""
                else:
                    reply = f"""{church} · {team["name"]}
Выберите роли кнопками. Нажмите повторно, чтобы снять выбор.

Выбрано: {names}

Права администратора назначаются отдельно."""
                    markup = {
                        "inline_keyboard": [
                            [
                                {
                                    "text": ("✓ " if role["id"] in selected else "") + role["name"],
                                    "callback_data": f"role:{ministry_id}:{role['id']}",
                                }
                            ]
                            for role in team["roles"]
                        ]
                        + [
                            [{"text": "Отправить заявку", "callback_data": f"apply:{ministry_id}"}],
                            [{"text": "Назад", "callback_data": "teams"}],
                        ]
                    }
                await telegram(
                    client,
                    settings,
                    "editMessageText",
                    {
                        "chat_id": chat_id,
                        "message_id": message["message_id"],
                        "text": reply[:4000],
                        "reply_markup": markup,
                    },
                )
                return
        else:
            reply = "Эта кнопка устарела. Откройте меню заново."
    except (ValueError, httpx.HTTPStatusError) as error:
        logger.warning("bot.callback_rejected", extra={"error_type": type(error).__name__})
        reply = "Не удалось выполнить действие. Попробуйте ещё раз через меню."
        if isinstance(error, ValueError):
            reply = str(error)
        elif error.response.status_code in {400, 403, 404, 409, 422}:
            detail = error.response.json().get("detail")
            if isinstance(detail, str):
                reply = detail
    await telegram(
        client,
        settings,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": reply[:4000],
            "reply_markup": markup,
        },
    )
