from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from worship_bot.infrastructure.models.base import Base, utc_now


class MinistryTypeRecord(Base):
    __tablename__ = "ministry_types"
    __table_args__ = (Index("uq_ministry_types_normalized_name", text("lower(name)"), unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ChurchMinistryRecord(Base):
    __tablename__ = "church_ministries"
    __table_args__ = (UniqueConstraint("church_id", "ministry_type_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    church_id: Mapped[int] = mapped_column(ForeignKey("churches.id", ondelete="CASCADE"))
    ministry_type_id: Mapped[int] = mapped_column(
        ForeignKey("ministry_types.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class MinistryMembershipRecord(Base):
    __tablename__ = "ministry_memberships"
    __table_args__ = (UniqueConstraint("church_ministry_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    church_ministry_id: Mapped[int] = mapped_column(
        ForeignKey("church_ministries.id", ondelete="CASCADE")
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    access_level: Mapped[str] = mapped_column(String(32), default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class MinistryRoleRecord(Base):
    __tablename__ = "ministry_roles"
    __table_args__ = (
        UniqueConstraint("church_ministry_id", "code"),
        UniqueConstraint("church_ministry_id", "name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    church_ministry_id: Mapped[int] = mapped_column(
        ForeignKey("church_ministries.id", ondelete="CASCADE")
    )
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(100))
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class UserMinistryRoleRecord(Base):
    __tablename__ = "user_ministry_roles"
    __table_args__ = (
        UniqueConstraint("ministry_membership_id", "ministry_role_id"),
        UniqueConstraint("church_membership_id", "ministry_role_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    allowed_event_kinds: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    church_membership_id: Mapped[int] = mapped_column(
        ForeignKey("church_memberships.id", ondelete="CASCADE")
    )
    ministry_membership_id: Mapped[int] = mapped_column(
        ForeignKey("ministry_memberships.id", ondelete="CASCADE")
    )
    ministry_role_id: Mapped[int] = mapped_column(
        ForeignKey("ministry_roles.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
