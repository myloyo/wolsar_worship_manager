from pydantic import BaseModel, Field

from worship_bot.domain.event_kinds import EventKind


class RoleEventKinds(BaseModel):
    allowed_event_kinds: list[EventKind] = Field(max_length=5)


class EventContentUpdate(BaseModel):
    revision: int = Field(ge=0)
    songs_text: str = Field(max_length=10000)
    clothing_text: str = Field(max_length=4000)


class EventKindUpdate(BaseModel):
    event_kind: EventKind


class EventNotificationUpdate(BaseModel):
    enabled: bool
