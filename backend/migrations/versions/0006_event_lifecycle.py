from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_event_lifecycle"
down_revision: str | None = "0005_ministry_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("events", sa.Column("rehearsal_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "events", sa.Column("event_reminder_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "events", sa.Column("rehearsal_reminder_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "event_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "user_ministry_role_id",
            sa.Integer(),
            sa.ForeignKey("user_ministry_roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "invited_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="invited"),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", "user_ministry_role_id"),
    )
    op.create_table(
        "event_song_set_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column(
            "edited_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", "version_number"),
    )
    op.create_table(
        "event_song_set_version_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "version_id",
            sa.Integer(),
            sa.ForeignKey("event_song_set_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "song_id", sa.Integer(), sa.ForeignKey("songs.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("version_id", "position"),
        sa.UniqueConstraint("version_id", "song_id"),
    )
    op.create_table(
        "notification_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("notification_type", sa.String(32), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("deduplication_key", sa.String(180), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute(
        """
        WITH versions AS (
            INSERT INTO event_song_set_versions
                (event_id, version_number, comment, created_at)
            SELECT event_id, 1, 'Initial song list', now()
            FROM event_songs
            GROUP BY event_id
            RETURNING id, event_id
        )
        INSERT INTO event_song_set_version_items (version_id, song_id, position)
        SELECT versions.id, event_songs.song_id, event_songs.position
        FROM versions
        JOIN event_songs ON event_songs.event_id = versions.event_id
        """
    )


def downgrade() -> None:
    op.drop_table("notification_jobs")
    op.drop_table("event_song_set_version_items")
    op.drop_table("event_song_set_versions")
    op.drop_table("event_invitations")
    op.drop_column("events", "rehearsal_reminder_at")
    op.drop_column("events", "event_reminder_at")
    op.drop_column("events", "rehearsal_at")
