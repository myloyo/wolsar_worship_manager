from collections.abc import Sequence

from alembic import op

revision: str = "0004_event_type_nullable"
down_revision: str | None = "0003_ministries_and_event_series"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("events", "event_type_id", nullable=True)


def downgrade() -> None:
    op.execute(
        """
        UPDATE events
        SET event_type_id = (SELECT id FROM event_types ORDER BY id LIMIT 1)
        WHERE event_type_id IS NULL
        """
    )
    op.alter_column("events", "event_type_id", nullable=False)
