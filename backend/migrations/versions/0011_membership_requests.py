import sqlalchemy as sa
from alembic import op

revision = "0011_membership_requests"
down_revision = "0010_web_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "church_id", existing_type=sa.Integer(), nullable=True)
    op.create_table(
        "membership_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "church_ministry_id",
            sa.Integer(),
            sa.ForeignKey("church_ministries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("role_ids", sa.JSON(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column(
            "decided_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "church_ministry_id"),
    )
    op.create_table(
        "account_link_codes",
        sa.Column("code_hash", sa.String(64), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # Keep accounts without a church intact; unsafe data loss is never an automatic downgrade.
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT count(*) FROM users WHERE church_id IS NULL")):
        raise RuntimeError("Move accounts without a church before downgrading this migration")
    op.drop_table("account_link_codes")
    op.drop_table("membership_requests")
    op.alter_column("users", "church_id", existing_type=sa.Integer(), nullable=False)
