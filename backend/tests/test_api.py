import pytest
from httpx import AsyncClient


@pytest.fixture
def event_series_payload() -> dict[str, object]:
    return {
        "event_name": "Воскресное прославление",
        "starts_at": "2026-11-01T10:00:00+04:00",
        "timezone": "Europe/Saratov",
        "recurrence_rule": "FREQ=WEEKLY;COUNT=2",
        "additional_info": "Репетиция за час",
        "song_ids": [501],
        "role_slots": [
            {
                "ministry_role_id": 1,
                "slot_number": 1,
                "user_ministry_role_id": 10,
            }
        ],
    }


async def test_health_endpoint_returns_healthy_status(api_client: AsyncClient) -> None:
    # Act
    response = await api_client.get("/health")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


async def test_assignment_for_unknown_event_returns_not_found(api_client: AsyncClient) -> None:
    # Act
    response = await api_client.post(
        "/api/v1/events/404/participants",
        json={"user_id": 1, "worship_role": "drums"},
    )

    # Assert
    assert response.status_code == 404
    assert response.json() == {"detail": "Event not found"}


async def test_create_church_returns_trimmed_name(api_client: AsyncClient) -> None:
    # Act
    response = await api_client.post("/api/v1/churches", json={"name": "  Новая церковь  "})

    # Assert
    assert response.status_code == 201
    assert response.json() == {"id": 2, "name": "Новая церковь"}


async def test_create_event_series_returns_songs(
    api_client: AsyncClient, event_series_payload: dict[str, object]
) -> None:
    # Act
    response = await api_client.post(
        "/api/v1/ministries/1/event-series",
        json=event_series_payload,
    )

    # Assert
    assert response.status_code == 201
    assert len(response.json()) == 2
    assert response.json()[0]["song_ids"] == [501]


async def test_list_calendar_returns_created_events(
    api_client: AsyncClient, event_series_payload: dict[str, object]
) -> None:
    # Arrange
    await api_client.post(
        "/api/v1/ministries/1/event-series",
        json=event_series_payload,
    )

    # Act
    calendar_response = await api_client.get(
        "/api/v1/calendar/events",
        params={
            "start": "2026-11-01T00:00:00+04:00",
            "end": "2026-11-30T23:59:00+04:00",
            "church_ministry_id": 1,
        },
    )

    # Assert
    assert calendar_response.status_code == 200
    assert len(calendar_response.json()) == 2
