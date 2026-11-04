from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from worship_bot.infrastructure.models.base import Base, utc_now


class ChurchRecord(Base):
    __tablename__ = "churches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ChurchMembershipRecord(Base):
    __tablename__ = "church_memberships"
    __table_args__ = (UniqueConstraint("church_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    church_id: Mapped[int] = mapped_column(ForeignKey("churches.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    access_level: Mapped[str] = mapped_column(String(32), default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    surname: Mapped[str] = mapped_column(String(100))
    church_id: Mapped[int | None] = mapped_column(
        ForeignKey("churches.id", ondelete="RESTRICT"), nullable=True
    )
    birthday_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    system_role: Mapped[str] = mapped_column(String(32), default="member")
    consent_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    worship_roles: Mapped[list[UserWorshipAssignmentRecord]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


class UserWorshipAssignmentRecord(Base):
    __tablename__ = "user_worship_assignments"
    __table_args__ = (UniqueConstraint("user_id", "worship_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    worship_role: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    user: Mapped[UserRecord] = relationship(back_populates="worship_roles")


class ExternalAccountRecord(Base):
    __tablename__ = "external_accounts"
    __table_args__ = (UniqueConstraint("provider", "external_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(16))
    external_user_id: Mapped[str] = mapped_column(String(128))
    username: Mapped[str | None] = mapped_column(String(150), nullable=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class RegistrationDraftRecord(Base):
    __tablename__ = "registration_drafts"
    __table_args__ = (UniqueConstraint("provider", "external_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(16))
    external_user_id: Mapped[str] = mapped_column(String(128))
    external_username: Mapped[str | None] = mapped_column(String(150), nullable=True)
    current_step: Mapped[str] = mapped_column(String(32), default="church")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    registration_data: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ConsentAcceptanceRecord(Base):
    __tablename__ = "consent_acceptances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    policy_version: Mapped[str] = mapped_column(String(32))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    provider: Mapped[str] = mapped_column(String(16))
