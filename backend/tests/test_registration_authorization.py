from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from worship_bot.api.dependencies import get_registration_service
from worship_bot.application.services import RegistrationService
from worship_bot.config import Settings, get_settings
from worship_bot.domain.entities import RegistrationDraft
from worship_bot.domain.enums import IdentityProvider, RegistrationStep
from worship_bot.main import app


@pytest.fixture
async def registration_client() -> AsyncIterator[tuple[AsyncClient, AsyncMock]]:
    previous = dict(app.dependency_overrides)
    service = AsyncMock(spec=RegistrationService)
    settings = Settings(bot_service_token=SecretStr("test-bot-token"))
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_registration_service] = lambda: service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, service
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.mark.parametrize("suffix", ["", "/1/steps", "/1/review", "/1/confirm"])
@pytest.mark.parametrize("token", [None, "incorrect-token"])
async def test_registration_routes_require_bot_authorization(
    registration_client: tuple[AsyncClient, AsyncMock],
    suffix: str,
    token: str | None,
) -> None:
    # Arrange
    client, service = registration_client
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # Act
    response = await client.post(
        f"/api/v1/internal/registrations{suffix}",
        json={},
        headers=headers,
    )

    # Assert
    assert response.status_code == 401
    assert service.mock_calls == []


async def test_registration_accepts_valid_bot_token(
    registration_client: tuple[AsyncClient, AsyncMock],
) -> None:
    # Arrange
    client, service = registration_client
    service.start.return_value = RegistrationDraft(
        1,
        IdentityProvider.TELEGRAM,
        "123",
        None,
        RegistrationStep.CHURCH,
        "pending",
        {},
    )
    payload = {"provider": "telegram", "external_user_id": "123"}
    headers = {"Authorization": "Bearer test-bot-token"}

    # Act
    response = await client.post(
        "/api/v1/internal/registrations",
        json=payload,
        headers=headers,
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["current_step"] == "church"
    service.start.assert_awaited_once()
