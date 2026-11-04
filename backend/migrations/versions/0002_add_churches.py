from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_churches"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "churches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column("users", sa.Column("church_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_users_church_id_churches",
        "users",
        "churches",
        ["church_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column("events", sa.Column("church_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_events_church_id_churches",
        "events",
        "churches",
        ["church_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_events_church_id_churches", "events", type_="foreignkey")
    op.drop_column("events", "church_id")
    op.drop_constraint("fk_users_church_id_churches", "users", type_="foreignkey")
    op.drop_column("users", "church_id")
    op.drop_table("churches")
