from typing import Literal

EventKind = Literal["sunday", "praise", "prayer", "leaders", "other"]


def infer_event_kind(name: str) -> EventKind:
    name = name.casefold()
    if "хвалы" in name or "вхм" in name:
        return "praise"
    if "лидер" in name or name.strip() == "ол":
        return "leaders"
    if "молитв" in name:
        return "prayer"
    if "воскрес" in name:
        return "sunday"
    return "other"


def role_allows_event(allowed_kinds: list[str], kind: str) -> bool:
    return not allowed_kinds or kind in allowed_kinds
