from datetime import datetime

import pytest
from worship_bot.domain.notifications import format_service_datetime


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-11-01T13:00:00+00:00", "1 ноября 2026, 17:00"),
        ("2026-11-04T06:00:00+00:00", "4 ноября 2026, 10:00"),
        ("2026-12-31T22:00:00+00:00", "1 января 2027, 02:00"),
    ],
)
def test_notification_dates_use_saratov_time(value: str, expected: str) -> None:
    # Act
    result = format_service_datetime(datetime.fromisoformat(value))

    # Assert
    assert result == expected


def test_notification_date_respects_event_timezone() -> None:
    # Arrange
    value = datetime.fromisoformat("2026-11-04T06:00:00+00:00")

    # Act
    result = format_service_datetime(value, "Europe/Moscow")

    # Assert
    assert result == "4 ноября 2026, 09:00"
