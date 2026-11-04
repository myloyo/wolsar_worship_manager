import sqlalchemy as sa
from alembic import op

revision = "0015_event_notifications"
down_revision = "0014_event_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_notification_preferences",
        sa.Column(
            "event_id",
            sa.Integer(),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("event_notification_preferences")
