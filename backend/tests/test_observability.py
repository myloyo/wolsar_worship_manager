import json
import logging
import sys
from collections.abc import Callable

import httpx
import pytest
from bot_service.clients import backend
from bot_service.config import BotSettings
from bot_service.observability import JsonLogFormatter as BotJsonLogFormatter
from bot_service.observability import request_id_context as bot_request_id_context
from fastapi import FastAPI
from pydantic import SecretStr
from worship_bot.api.request_logging import RequestLoggingMiddleware
from worship_bot.observability import JsonLogFormatter, request_id_context


@pytest.mark.parametrize("formatter", [JsonLogFormatter, BotJsonLogFormatter])
def test_json_logs_keep_stack_locations_but_omit_secrets(
    formatter: Callable[[str], logging.Formatter],
) -> None:
    # Arrange
    try:
        raise RuntimeError("password=private-secret https://example.test/#code=private")
    except RuntimeError:
        record = logging.LogRecord(
            "application",
            logging.ERROR,
            __file__,
            1,
            "operation.failed",
            ("private-token",),
            sys.exc_info(),
        )
    record.password = "private-secret"

    # Act
    output = formatter("service").format(record)
    data = json.loads(output)

    # Assert
    assert data["event"] == "operation.failed"
    assert data["error_type"] == "RuntimeError"
    assert data["stack"][0]["function"] == "test_json_logs_keep_stack_locations_but_omit_secrets"
    assert "private" not in output
    assert "https://" not in output


async def test_http_logs_template_and_safe_error_without_request_secrets(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Arrange
    application = FastAPI()
    application.add_middleware(RequestLoggingMiddleware)

    @application.post("/example/{item_id}")
    async def example(item_id: int) -> None:
        raise RuntimeError(f"private-secret for {item_id}")

    caplog.set_level(logging.INFO, logger="worship_bot.api.request_logging")

    # Act
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/example/42?code=private-secret",
            json={"password": "private-secret"},
            headers={"Authorization": "Bearer private-secret", "X-Request-ID": "a" * 32},
        )
    records = [
        record for record in caplog.records if record.name == "worship_bot.api.request_logging"
    ]
    output = "\n".join(JsonLogFormatter("api").format(record) for record in records)

    # Assert
    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "a" * 32
    assert response.json() == {"detail": "Внутренняя ошибка сервера"}
    assert "private-secret" not in output
    assert '"route": "/example/{item_id}"' in output
    assert any(getattr(record, "status_code", None) == 500 for record in records)
    assert request_id_context.get() == ""


async def test_bot_backend_request_propagates_correlation_id_without_logging_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Arrange
    settings = BotSettings(bot_service_token=SecretStr("private-service-secret"))
    request_ids: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        request_ids.append(request.headers["X-Request-ID"])
        return httpx.Response(200, json={"ok": True})

    token = bot_request_id_context.set("b" * 32)
    caplog.set_level(logging.INFO, logger="bot_service.clients")

    # Act
    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            await backend(client, settings, "POST", "/internal/bot/login", {"code": "private-code"})
    finally:
        bot_request_id_context.reset(token)
    output = "\n".join(BotJsonLogFormatter("bot").format(record) for record in caplog.records)

    # Assert
    assert request_ids == ["b" * 32]
    assert "private" not in output
    assert "backend.request_completed" in output
