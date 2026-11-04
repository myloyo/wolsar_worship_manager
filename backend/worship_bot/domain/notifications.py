from datetime import UTC, datetime
from zoneinfo import ZoneInfo

MONTHS = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def format_service_datetime(value: datetime, timezone: str = "Europe/Saratov") -> str:
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    local = aware.astimezone(ZoneInfo(timezone))
    return f"{local.day} {MONTHS[local.month - 1]} {local.year}, {local:%H:%M}"


def assignment_revision(value: datetime) -> str:
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).strftime("%Y%m%d%H%M%S%f")
