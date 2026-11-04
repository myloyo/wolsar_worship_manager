from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from worship_bot.infrastructure.models.base import Base, utc_now


class EventTypeRecord(Base):
    __tablename__ = "event_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    custom_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_default: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class EventSeriesRecord(Base):
    __tablename__ = "event_series"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    church_ministry_id: Mapped[int] = mapped_column(
        ForeignKey("church_ministries.id", ondelete="CASCADE")
    )
    event_name: Mapped[str] = mapped_column(String(150))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Saratov")
    recurrence_rule: Mapped[str | None] = mapped_column(String(500), nullable=True)
    repeats_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    additional_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class EventRecord(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_name: Mapped[str] = mapped_column(String(150))
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    event_type_id: Mapped[int | None] = mapped_column(ForeignKey("event_types.id"), nullable=True)
    church_id: Mapped[int] = mapped_column(
        ForeignKey("churches.id", ondelete="RESTRICT"), nullable=False
    )
    church_ministry_id: Mapped[int | None] = mapped_column(
        ForeignKey("church_ministries.id", ondelete="RESTRICT"), nullable=True
    )
    event_series_id: Mapped[int | None] = mapped_column(
        ForeignKey("event_series.id", ondelete="CASCADE"), nullable=True
    )
    additional_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    rehearsal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_kind: Mapped[str] = mapped_column(String(32), default="other", server_default="other")
    songs_text: Mapped[str] = mapped_column(Text, default="", server_default="")
    clothing_text: Mapped[str] = mapped_column(Text, default="", server_default="")
    content_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    event_reminder_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rehearsal_reminder_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class EventRoleSlotRecord(Base):
    __tablename__ = "event_role_slots"
    __table_args__ = (UniqueConstraint("event_id", "ministry_role_id", "slot_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    ministry_role_id: Mapped[int] = mapped_column(
        ForeignKey("ministry_roles.id", ondelete="RESTRICT")
    )
    slot_number: Mapped[int] = mapped_column(Integer, default=1)
    user_ministry_role_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_ministry_roles.id", ondelete="SET NULL"), nullable=True
    )
    confirmation_status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class EventParticipantRecord(Base):
    __tablename__ = "event_participants"
    __table_args__ = (UniqueConstraint("event_id", "user_id", "worship_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    worship_role: Mapped[str] = mapped_column(String(32))
    confirmation_status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class EventInvitationRecord(Base):
    __tablename__ = "event_invitations"
    __table_args__ = (UniqueConstraint("event_id", "user_ministry_role_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    user_ministry_role_id: Mapped[int] = mapped_column(
        ForeignKey("user_ministry_roles.id", ondelete="CASCADE")
    )
    invited_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default="invited")
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
