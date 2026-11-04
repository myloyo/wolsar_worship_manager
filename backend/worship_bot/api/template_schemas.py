from pydantic import BaseModel, Field, field_validator

from worship_bot.api.schemas import EventRoleSlotCreate


class EventTemplateData(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    additional_info: str | None = Field(default=None, max_length=10000)
    rehearsal_offset_minutes: int | None = Field(default=None, ge=0, le=10080)
    role_slots: list[EventRoleSlotCreate] = Field(default_factory=list, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Укажите название шаблона")
        return value.strip()


class EventTemplateRead(EventTemplateData):
    id: str
    builtin: bool = False


def default_event_templates() -> list[EventTemplateRead]:
    return [
        EventTemplateRead(id=code, name=name, builtin=True)
        for code, name in (
            ("sunday-meeting", "Воскресное собрание"),
            ("sunday-prayer", "Воскресная молитва"),
            ("leaders-meeting", "Общее лидерское собрание"),
            ("praise-and-prayer", "Вечер хвалы и молитвы"),
        )
    ]
