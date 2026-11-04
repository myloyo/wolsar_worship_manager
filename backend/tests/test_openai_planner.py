import json
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from worship_bot.application.exceptions import PlanningProviderError
from worship_bot.config import Settings
from worship_bot.infrastructure.openai_planner import generate_proposal


async def test_planner_uses_responses_with_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    captured: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        proposal = {"reply": "Нужна история", "warnings": ["Истории нет"], "events": []}
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [{"content": [{"type": "output_text", "text": json.dumps(proposal)}]}],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(
        "worship_bot.infrastructure.openai_planner.httpx.AsyncClient", lambda **kwargs: client
    )
    settings = Settings(openai_api_key=SecretStr("test-key"), openai_model="test-model")

    # Act
    proposal = await generate_proposal(
        settings, {"month": "2026-11"}, [{"role": "user", "content": "Заполни месяц"}], []
    )

    # Assert
    assert proposal.events == []
    assert captured[0]["model"] == "test-model"
    assert captured[0]["store"] is False
    assert captured[0]["text"]["format"]["strict"] is True
    assert captured[0]["text"]["format"]["schema"]["additionalProperties"] is False


@pytest.mark.parametrize(
    ("status", "code", "expected"),
    [
        (401, "invalid_api_key", "API-ключ"),
        (403, "unsupported_country_region_territory", "региона сервера"),
        (404, "model_not_found", "недоступна этому проекту"),
        (429, "insufficient_quota", "Закончились кредиты"),
        (429, "rate_limit_exceeded", "временный лимит"),
        (400, "invalid_json_schema", "формат запроса"),
        (503, "server_error", "стороне OpenAI"),
    ],
)
async def test_provider_errors_are_specific_and_logs_do_not_expose_data(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    status: int,
    code: str,
    expected: str,
) -> None:
    # Arrange
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            headers={"x-request-id": "req_unit"},
            json={
                "error": {
                    "code": code,
                    "param": "input",
                    "message": "private-history secret-unit-api-key",
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(
        "worship_bot.infrastructure.openai_planner.httpx.AsyncClient", lambda **kwargs: client
    )
    settings = Settings(openai_api_key=SecretStr("secret-unit-api-key"))

    # Act / Assert
    with pytest.raises(PlanningProviderError, match=expected):
        await generate_proposal(settings, {}, [{"role": "user", "content": "private-history"}], [])
    assert any(
        getattr(record, "status_code", None) == status
        and getattr(record, "error_code", None) == code
        for record in caplog.records
    )
    assert any(
        getattr(record, "provider_request_id", None) == "req_unit" for record in caplog.records
    )
    assert "private-history" not in caplog.text and "secret-unit-api-key" not in caplog.text


@pytest.mark.parametrize(
    ("error_type", "code"), [(httpx.ConnectError, "network"), (httpx.ReadTimeout, "timeout")]
)
async def test_network_failures_do_not_suggest_changing_the_api_key(
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[httpx.RequestError],
    code: str,
) -> None:
    # Arrange
    def respond(request: httpx.Request) -> httpx.Response:
        raise error_type("private network details", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(
        "worship_bot.infrastructure.openai_planner.httpx.AsyncClient", lambda **kwargs: client
    )

    # Act / Assert
    with pytest.raises(PlanningProviderError) as result:
        await generate_proposal(Settings(openai_api_key=SecretStr("unit-key")), {}, [], [])
    assert result.value.code == code
    assert "API-ключ" not in str(result.value)


async def test_incomplete_result_reports_its_reason(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Arrange
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "status": "incomplete",
                    "incomplete_details": {"reason": "max_output_tokens"},
                },
            )
        )
    )
    monkeypatch.setattr(
        "worship_bot.infrastructure.openai_planner.httpx.AsyncClient", lambda **kwargs: client
    )

    # Act / Assert
    with pytest.raises(PlanningProviderError, match="не завершила"):
        await generate_proposal(Settings(openai_api_key=SecretStr("unit-key")), {}, [], [])
    assert any(
        getattr(record, "error_code", None) == "max_output_tokens" for record in caplog.records
    )
