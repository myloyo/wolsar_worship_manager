import sqlalchemy as sa
from alembic import op

revision = "0013_ministry_names"
down_revision = "0012_worship_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_ministry_types_normalized_name",
        "ministry_types",
        [sa.text("lower(name)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_ministry_types_normalized_name", table_name="ministry_types")
