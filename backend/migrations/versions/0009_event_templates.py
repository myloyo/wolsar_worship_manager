import sqlalchemy as sa
from alembic import op

revision = "0009_event_templates"
down_revision = "0008_web_push"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "church_ministry_id",
            sa.Integer(),
            sa.ForeignKey("church_ministries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_event_templates_church_ministry_id", "event_templates", ["church_ministry_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_event_templates_church_ministry_id", table_name="event_templates")
    op.drop_table("event_templates")
