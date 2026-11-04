from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from worship_bot.infrastructure.models.base import Base, utc_now


class LoginCodeRecord(Base):
    __tablename__ = "login_codes"
    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AssistantSessionRecord(Base):
    __tablename__ = "assistant_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    church_ministry_id: Mapped[int] = mapped_column(
        ForeignKey("church_ministries.id", ondelete="CASCADE")
    )
    month: Mapped[str] = mapped_column(String(7))
    messages: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    attachments: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    proposal: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
