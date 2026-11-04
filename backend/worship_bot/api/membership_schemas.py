from datetime import datetime

from pydantic import BaseModel, Field

from worship_bot.api.schemas import BotIdentity


class JoinRequest(BaseModel):
    role_ids: list[int] = Field(default_factory=list, max_length=30)
    message: str | None = Field(default=None, max_length=2000)


class JoinDecision(JoinRequest):
    approve: bool


class DirectoryRole(BaseModel):
    id: int
    name: str


class DirectoryTeam(BaseModel):
    id: int
    name: str
    roles: list[DirectoryRole]
    status: str
    decision_note: str | None = None


class DirectoryChurch(BaseModel):
    id: int
    name: str
    teams: list[DirectoryTeam]


class MembershipRequestRead(BaseModel):
    id: int
    user_id: int
    name: str
    surname: str
    role_ids: list[int]
    message: str | None
    created_at: datetime


class AccountLinkCreate(BaseModel):
    url: str
    expires_at: datetime


class BotAccountLink(BotIdentity):
    code: str = Field(min_length=20, max_length=64)
    username: str | None = Field(default=None, max_length=150)


class AccountConnections(BaseModel):
    telegram_linked: bool
    telegram_username: str | None


class BotJoinRequest(BotIdentity, JoinRequest):
    church_ministry_id: int = Field(gt=0)
