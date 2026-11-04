import json
from typing import Any

import httpx
import pytest
from bot_service.clients import telegram
from bot_service.config import BotSettings
from bot_service.handlers.callbacks import handle_callback
from bot_service.handlers.messages import handle_message
from bot_service.handlers.updates import handle_update
from bot_service.keyboards import invitation_keyboard, menu_keyboard, supports_url_button
from pydantic import SecretStr


async def test_bot_does_not_process_group_messages() -> None:
    # Arrange
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {}})

    settings = BotSettings(
        telegram_bot_token=SecretStr("test"), bot_service_token=SecretStr("test")
    )

    # Act
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await handle_message(
            client,
            settings,
            {"chat": {"type": "group", "id": 1}, "from": {"id": 2}, "text": "/login"},
        )

    # Assert
    assert requests == []


async def test_login_uses_telegram_sender_identity() -> None:
    # Arrange
    bodies: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        if request.url.path.endswith("/login"):
            return httpx.Response(200, json={"url": "http://localhost/#code=test"})
        return httpx.Response(200, json={"ok": True, "result": {}})

    settings = BotSettings(
        telegram_bot_token=SecretStr("test"), bot_service_token=SecretStr("test")
    )

    # Act
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await handle_message(
            client,
            settings,
            {"chat": {"type": "private", "id": 42}, "from": {"id": 7}, "text": "/login"},
        )

    # Assert
    assert bodies[0]["external_user_id"] == "7"
    assert bodies[1]["chat_id"] == 42
    assert "#code=test" in bodies[1]["text"]


async def test_telegram_link_uses_sender_identity() -> None:
    # Arrange
    bodies: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        if request.url.path.endswith("/link"):
            return httpx.Response(200, json={"url": "http://localhost/#code=sample"})
        return httpx.Response(200, json={"ok": True, "result": {}})

    settings = BotSettings(
        telegram_bot_token=SecretStr("sample"), bot_service_token=SecretStr("sample")
    )

    # Act
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await handle_message(
            client,
            settings,
            {
                "chat": {"type": "private", "id": 42},
                "from": {"id": 7, "username": "person"},
                "text": "/start link_linking-code-value",
            },
        )

    # Assert
    assert bodies[0]["external_user_id"] == "7"
    assert bodies[0]["code"] == "linking-code-value"
    assert "привязан" in bodies[1]["text"]


async def test_bot_registration_redirects_to_site() -> None:
    # Arrange
    messages: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.telegram.org"
        messages.append(json.loads(request.content)["text"])
        return httpx.Response(200, json={"ok": True, "result": {}})

    settings = BotSettings(
        telegram_bot_token=SecretStr("sample"), bot_service_token=SecretStr("sample")
    )

    # Act
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await handle_message(
            client,
            settings,
            {"chat": {"type": "private", "id": 42}, "from": {"id": 7}, "text": "/register"},
        )

    # Assert
    assert "Регистрация проходит на сайте" in messages[0]


async def test_role_buttons_toggle_names_then_submit_application() -> None:
    # Arrange
    sent: list[dict[str, Any]] = []
    applications: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.url.path.endswith("/directory"):
            return httpx.Response(
                200,
                json=[
                    {
                        "name": "Церковь",
                        "teams": [
                            {
                                "id": 3,
                                "name": "Прославление",
                                "status": "none",
                                "roles": [{"id": 21, "name": "Танцы"}, {"id": 22, "name": "Вокал"}],
                            }
                        ],
                    }
                ],
            )
        if request.url.path.endswith("/applications"):
            applications.append(body)
            return httpx.Response(204)
        sent.append(body)
        return httpx.Response(200, json={"ok": True, "result": {}})

    settings = BotSettings(
        telegram_bot_token=SecretStr("sample"), bot_service_token=SecretStr("sample")
    )
    callback: dict[str, Any] = {
        "id": "query",
        "from": {"id": 7},
        "data": "role:3:21",
        "message": {
            "message_id": 9,
            "chat": {"type": "private", "id": 42},
            "reply_markup": {
                "inline_keyboard": [[{"text": "Танцы", "callback_data": "role:3:21"}]]
            },
        },
    }

    # Act
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await handle_callback(client, settings, callback)
        selection = sent[-1]
        callback["data"] = "apply:3"
        callback["message"]["reply_markup"] = selection["reply_markup"]
        await handle_callback(client, settings, callback)

    # Assert
    assert "Выбрано: Танцы" in selection["text"]
    assert selection["reply_markup"]["inline_keyboard"][0][0]["text"] == "✓ Танцы"
    assert applications == [
        {"provider": "telegram", "external_user_id": "7", "church_ministry_id": 3, "role_ids": [21]}
    ]
    assert "Заявка отправлена" in sent[-1]["text"]
    assert "role_ids" not in sent[-1]["text"]


async def test_invitation_button_uses_sender_and_removes_old_actions() -> None:
    # Arrange
    requests: list[tuple[str, dict[str, Any]]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"ok": True, "result": {}})

    settings = BotSettings(
        telegram_bot_token=SecretStr("sample"), bot_service_token=SecretStr("sample")
    )
    callback: dict[str, Any] = {
        "id": "query",
        "from": {"id": 7},
        "data": "invite:accept:15",
        "message": {
            "message_id": 9,
            "chat": {"type": "private", "id": 42},
        },
    }

    # Act
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await handle_callback(client, settings, callback)

    # Assert
    assert requests[0][0].endswith("/answerCallbackQuery")
    assert requests[1][1] == {
        "provider": "telegram",
        "external_user_id": "7",
        "invitation_id": 15,
        "accept": True,
    }
    assert requests[2][1]["reply_markup"] == {"inline_keyboard": []}
    assert "подтверждено" in requests[3][1]["text"]
    assert invitation_keyboard(15)["inline_keyboard"][0][0]["text"] == "Подтвердить участие"


async def test_bot_rejects_forged_role_from_another_team() -> None:
    # Arrange
    sent: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/directory"):
            return httpx.Response(
                200,
                json=[
                    {
                        "name": "Церковь",
                        "teams": [
                            {
                                "id": 3,
                                "name": "Прославление",
                                "status": "none",
                                "roles": [],
                            }
                        ],
                    }
                ],
            )
        assert not request.url.path.endswith("/applications")
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {}})

    settings = BotSettings(
        telegram_bot_token=SecretStr("sample"), bot_service_token=SecretStr("sample")
    )

    # Act
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await handle_callback(
            client,
            settings,
            {
                "id": "query",
                "from": {"id": 7},
                "data": "role:3:999",
                "message": {
                    "message_id": 9,
                    "chat": {"type": "private", "id": 42},
                },
            },
        )

    # Assert
    assert "роль больше недоступна" in sent[-1]["text"]


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://192.168.1.5",
        "http://[::1]",
        "http://frontend:8080",
    ],
)
def test_local_urls_are_not_used_in_telegram_buttons(url: str) -> None:
    # Act
    markup = menu_keyboard(url)

    # Assert
    assert not supports_url_button(url)
    assert all("url" not in button for row in markup["inline_keyboard"] for button in row)
    assert markup["inline_keyboard"][-1][0]["callback_data"] == "website"


async def test_public_login_link_remains_a_button() -> None:
    # Arrange
    messages: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/login"):
            return httpx.Response(200, json={"url": "https://worship.example/#code=sample"})
        messages.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {}})

    settings = BotSettings(
        telegram_bot_token=SecretStr("sample"), bot_service_token=SecretStr("sample")
    )

    # Act
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await handle_message(
            client,
            settings,
            {"chat": {"type": "private", "id": 1}, "from": {"id": 2}, "text": "/login"},
        )

    # Assert
    assert messages[0]["reply_markup"]["inline_keyboard"][0][0]["url"].startswith(
        "https://worship.example/"
    )


async def test_invalid_message_does_not_block_next_update() -> None:
    # Arrange
    messages: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/profile"):
            return httpx.Response(404, json={"detail": "Привяжите Telegram"})
        messages.append(json.loads(request.content)["text"])
        if len(messages) == 1:
            return httpx.Response(
                400, json={"ok": False, "description": "Bad Request: invalid button"}
            )
        return httpx.Response(200, json={"ok": True, "result": {}})

    settings = BotSettings(
        telegram_bot_token=SecretStr("sample"), bot_service_token=SecretStr("sample")
    )

    # Act
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        for number in (1, 2):
            await handle_update(
                client,
                settings,
                {
                    "update_id": number,
                    "message": {
                        "chat": {"type": "private", "id": 1},
                        "from": {"id": 2},
                        "text": "/start",
                    },
                },
            )

    # Assert
    assert len(messages) == 2


async def test_telegram_error_log_redacts_tokens_and_urls(caplog: pytest.LogCaptureFixture) -> None:
    # Arrange
    settings = BotSettings(
        telegram_bot_token=SecretStr("fake-secret"), bot_service_token=SecretStr("other-secret")
    )

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "ok": False,
                "description": (
                    "Wrong URL https://example.com/#code=private fake-secret other-secret"
                ),
            },
        )

    # Act
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await telegram(client, settings, "sendMessage", {})

    # Assert
    assert any(getattr(record, "operation", None) == "sendMessage" for record in caplog.records)
    assert "fake-secret" not in caplog.text and "other-secret" not in caplog.text
    assert "code=private" not in caplog.text


@pytest.mark.parametrize("status", [429, 500])
async def test_temporary_delivery_errors_remain_retryable(status: int) -> None:
    # Arrange
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"ok": False, "description": "Try later"})

    settings = BotSettings(
        telegram_bot_token=SecretStr("sample"), bot_service_token=SecretStr("sample")
    )

    # Act / Assert
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await handle_update(
                client,
                settings,
                {
                    "update_id": 1,
                    "message": {
                        "chat": {"type": "private", "id": 1},
                        "from": {"id": 2},
                        "text": "/register",
                    },
                },
            )


async def test_website_button_returns_link_without_stale_message() -> None:
    # Arrange
    sent: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {}})

    settings = BotSettings(
        telegram_bot_token=SecretStr("sample"),
        bot_service_token=SecretStr("sample"),
        web_url="http://localhost:8080",
    )

    # Act
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await handle_callback(
            client,
            settings,
            {
                "id": "query",
                "from": {"id": 7},
                "data": "website",
                "message": {"message_id": 9, "chat": {"type": "private", "id": 42}},
            },
        )

    # Assert
    assert sent[-1]["text"] == "Сайт: http://localhost:8080"
    assert "устарела" not in sent[-1]["text"]


async def test_assignment_button_sends_authenticated_response() -> None:
    # Arrange
    bodies: list[tuple[str, dict[str, Any]]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        bodies.append((request.url.path, json.loads(request.content)))
        if request.url.path.endswith("/respond"):
            return httpx.Response(204)
        return httpx.Response(200, json={"ok": True, "result": {}})

    settings = BotSettings(
        telegram_bot_token=SecretStr("sample"), bot_service_token=SecretStr("sample")
    )

    # Act
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await handle_callback(
            client,
            settings,
            {
                "id": "query",
                "from": {"id": 7},
                "data": "assignment:accept:12:20261101000000000000",
                "message": {"message_id": 9, "chat": {"type": "private", "id": 42}},
            },
        )

    # Assert
    assert bodies[1][0].endswith("/assignments/respond")
    assert bodies[1][1] == {
        "provider": "telegram",
        "external_user_id": "7",
        "slot_id": 12,
        "revision": "20261101000000000000",
        "accept": True,
    }
    assert bodies[2][1]["reply_markup"] == {"inline_keyboard": []}
    assert "подтверждено" in bodies[-1][1]["text"]
