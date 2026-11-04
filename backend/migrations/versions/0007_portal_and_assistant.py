import sqlalchemy as sa
from alembic import op

revision = "0007_portal_and_assistant"
down_revision = "0006_event_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("notification_jobs", sa.Column("claim_token", sa.String(64), nullable=True))
    op.add_column(
        "notification_jobs", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "login_codes",
        sa.Column("code_hash", sa.String(64), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_login_codes_expires_at", "login_codes", ["expires_at"])
    op.create_table(
        "assistant_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "church_ministry_id",
            sa.Integer(),
            sa.ForeignKey("church_ministries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("month", sa.String(7), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("attachments", sa.JSON(), nullable=False),
        sa.Column("proposal", sa.JSON(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("notification_jobs", "locked_until")
    op.drop_column("notification_jobs", "claim_token")
    op.drop_table("assistant_sessions")
    op.drop_index("ix_login_codes_expires_at", table_name="login_codes")
    op.drop_table("login_codes")
