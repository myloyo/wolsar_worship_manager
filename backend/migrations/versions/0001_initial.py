from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("surname", sa.String(100), nullable=False),
        sa.Column("birthday_date", sa.Date(), nullable=True),
        sa.Column("system_role", sa.String(32), nullable=False, server_default="member"),
        sa.Column("consent_approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "user_worship_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("worship_role", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "worship_role"),
    )
    op.create_table(
        "event_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("custom_name", sa.String(150), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_name", sa.String(150), nullable=False),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type_id", sa.Integer(), sa.ForeignKey("event_types.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "event_participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("worship_role", sa.String(32), nullable=False),
        sa.Column("confirmation_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", "user_id", "worship_role"),
    )
    op.create_table(
        "songs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("song_name", sa.String(200), nullable=False),
        sa.Column("song_lyric", sa.Text(), nullable=True),
        sa.Column("youtube_url", sa.String(500), nullable=True),
        sa.Column("vocals_line", sa.String(100), nullable=True),
        sa.Column("bpm", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "event_songs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "song_id", sa.Integer(), sa.ForeignKey("songs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", "song_id"),
    )
    op.create_table(
        "songs_key_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "song_id", sa.Integer(), sa.ForeignKey("songs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("song_key_version", sa.String(16), nullable=False),
        sa.Column("audio_file_link", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    event_types = sa.table(
        "event_types",
        sa.column("code", sa.String),
        sa.column("custom_name", sa.String),
        sa.column("is_default", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        event_types,
        [
            {
                "code": code,
                "custom_name": None,
                "is_default": True,
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }
            for code in (
                "sunday_service",
                "wednesday_prayer",
                "worship_night",
                "youth",
                "christmas",
                "easter",
                "new_year_prayer",
                "youth_conference",
                "conference",
                "seminar",
            )
        ],
    )


def downgrade() -> None:
    op.drop_table("songs_key_versions")
    op.drop_table("event_songs")
    op.drop_table("songs")
    op.drop_table("event_participants")
    op.drop_table("events")
    op.drop_table("event_types")
    op.drop_table("user_worship_assignments")
    op.drop_table("users")
