from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class PlannedAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ministry_role_id: int = Field(gt=0)
    user_ministry_role_id: int = Field(gt=0)


class PlannedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    existing_event_id: int | None
    event_name: str = Field(min_length=1, max_length=150)
    starts_at: AwareDatetime
    additional_info: str | None
    assignments: list[PlannedAssignment] = Field(max_length=50)


class ScheduleProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reply: str
    warnings: list[str]
    events: list[PlannedEvent] = Field(max_length=62)
