import sqlalchemy as sa
from alembic import op

revision = "0014_event_preferences"
down_revision = "0013_ministry_names"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "events", sa.Column("event_kind", sa.String(32), nullable=False, server_default="other")
    )
    op.add_column("events", sa.Column("songs_text", sa.Text(), nullable=False, server_default=""))
    op.add_column(
        "events", sa.Column("clothing_text", sa.Text(), nullable=False, server_default="")
    )
    op.add_column(
        "events", sa.Column("content_revision", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "user_ministry_roles",
        sa.Column("allowed_event_kinds", sa.JSON(), nullable=False, server_default="[]"),
    )
    events = sa.table(
        "events",
        sa.column("id", sa.Integer),
        sa.column("event_name", sa.String),
        sa.column("event_kind", sa.String),
    )
    name = sa.func.lower(events.c.event_name)
    op.execute(
        events.update().values(
            event_kind=sa.case(
                (sa.or_(name.like("%хвалы%"), name.like("%вхм%")), "praise"),
                (sa.or_(name.like("%лидер%"), sa.func.trim(name) == "ол"), "leaders"),
                (name.like("%молитв%"), "prayer"),
                (name.like("%воскрес%"), "sunday"),
                else_="other",
            )
        )
    )


def downgrade() -> None:
    op.drop_column("user_ministry_roles", "allowed_event_kinds")
    for column in ("content_revision", "clothing_text", "songs_text", "event_kind"):
        op.drop_column("events", column)
