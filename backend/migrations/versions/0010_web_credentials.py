import sqlalchemy as sa
from alembic import op

revision = "0010_web_credentials"
down_revision = "0009_event_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "web_credentials",
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("login", sa.String(64), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("web_credentials")
