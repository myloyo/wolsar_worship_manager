from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from worship_bot.domain.planning import ScheduleProposal


def validate_proposal(
    proposal: ScheduleProposal,
    month: str,
    members: list[dict[str, Any]],
    existing_events: list[dict[str, Any]],
) -> None:
    role_owners = {
        role["user_ministry_role_id"]: (member["id"], role["id"])
        for member in members
        for role in member["roles"]
    }
    events = {event["event_id"]: event for event in existing_events}
    seen_events: set[int] = set()
    seen_dates: set[datetime] = set()
    for event in proposal.events:
        if event.starts_at.astimezone(ZoneInfo("Europe/Saratov")).strftime("%Y-%m") != month:
            raise ValueError("Все события должны относиться к выбранному месяцу")
        if event.starts_at in seen_dates:
            raise ValueError("В черновике повторяется время события")
        seen_dates.add(event.starts_at)
        if event.existing_event_id is not None:
            if event.existing_event_id not in events or event.existing_event_id in seen_events:
                raise ValueError("Событие не принадлежит этому календарю или повторяется")
            if (
                datetime.fromisoformat(events[event.existing_event_id]["starts_at"])
                != event.starts_at
            ):
                raise ValueError("Изменение даты существующего события не поддерживается")
            seen_events.add(event.existing_event_id)
        people: set[int] = set()
        roles: set[int] = set()
        for assignment in event.assignments:
            owner = role_owners.get(assignment.user_ministry_role_id)
            if owner is None or owner[1] != assignment.ministry_role_id:
                raise ValueError("Участник не имеет указанной роли в служении")
            if owner[0] in people or assignment.ministry_role_id in roles:
                raise ValueError("Повторяется участник или роль в одном событии")
            people.add(owner[0])
            roles.add(assignment.ministry_role_id)
