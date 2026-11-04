from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from worship_bot.infrastructure.models.base import Base, utc_now


class EventTemplateRecord(Base):
    __tablename__ = "event_templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    church_ministry_id: Mapped[int] = mapped_column(
        ForeignKey("church_ministries.id", ondelete="CASCADE"), index=True
    )
    details: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
