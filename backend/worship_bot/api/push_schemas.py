from typing import Literal

from pydantic import BaseModel, Field


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=80, max_length=128, pattern=r"^[A-Za-z0-9_-]+={0,2}$")
    auth: str = Field(min_length=20, max_length=64, pattern=r"^[A-Za-z0-9_-]+={0,2}$")


class PushRegistration(BaseModel):
    endpoint: str = Field(min_length=20, max_length=2048)
    keys: PushKeys


class PushState(BaseModel):
    endpoint: str = Field(max_length=2048)
    permission: Literal["granted", "denied", "default", "unsupported"]
