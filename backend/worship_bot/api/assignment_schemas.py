from datetime import datetime

from pydantic import BaseModel, Field

from worship_bot.api.schemas import BotIdentity


class AssignmentResponse(BaseModel):
    accept: bool
    revision: str = Field(pattern=r"^[0-9]{20}$")


class BotAssignmentResponse(BotIdentity, AssignmentResponse):
    slot_id: int = Field(gt=0)


class MyAssignment(BaseModel):
    songs_text: str = ""
    clothing_text: str = ""
    slot_id: int
    event_id: int
    event_name: str
    church_name: str
    ministry_name: str
    role_name: str
    starts_at: datetime
    rehearsal_at: datetime | None
    additional_info: str | None
    status: str
    revision: str
