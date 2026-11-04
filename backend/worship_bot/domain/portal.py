from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class MemberRole:
    id: int
    name: str
    user_ministry_role_id: int
    allowed_event_kinds: list[str] = field(default_factory=list)


@dataclass
class Member:
    id: int
    name: str
    surname: str
    access_level: str
    roles: list[MemberRole]
    notification_status: str = "needs_setup"
    notifications_checked_at: datetime | None = None


@dataclass
class MinistrySummary:
    id: int
    name: str
    church_name: str
    access_level: str
    permissions: list[str]


@dataclass
class Profile:
    id: int
    name: str
    surname: str
    birthday_date: date | None
    ministries: list[MinistrySummary]


def permissions_for(access_level: str | None) -> list[str]:
    if access_level is None:
        return []
    permissions = ["view_schedule", "view_members", "self_signup"]
    if access_level in {"coordinator", "admin", "developer"}:
        permissions += ["manage_events", "manage_assignments"]
    if access_level in {"admin", "developer"}:
        permissions += ["use_assistant", "manage_members"]
    return permissions


@dataclass
class LoginTicket:
    code: str
    expires_at: datetime
