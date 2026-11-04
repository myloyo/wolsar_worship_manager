from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_ministry_identity"
down_revision: str | None = "0004_event_type_nullable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ministry_types",
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ministry_types_created_by_user_id_users",
        "ministry_types",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "ministry_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "church_ministry_id",
            sa.Integer(),
            sa.ForeignKey("church_ministries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("access_level", sa.String(32), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("church_ministry_id", "user_id"),
    )
    op.execute(
        """
        INSERT INTO ministry_memberships
            (church_ministry_id, user_id, access_level, created_at, updated_at)
        SELECT church_ministries.id, church_memberships.user_id, 'member', now(), now()
        FROM church_ministries
        JOIN church_memberships ON church_memberships.church_id = church_ministries.church_id
        ON CONFLICT (church_ministry_id, user_id) DO NOTHING
        """
    )
    op.add_column(
        "user_ministry_roles",
        sa.Column("ministry_membership_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_user_ministry_roles_ministry_membership_id",
        "user_ministry_roles",
        "ministry_memberships",
        ["ministry_membership_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.execute(
        """
        UPDATE user_ministry_roles
        SET ministry_membership_id = ministry_memberships.id
        FROM church_memberships, ministry_roles, church_ministries, ministry_memberships
        WHERE user_ministry_roles.church_membership_id = church_memberships.id
          AND user_ministry_roles.ministry_role_id = ministry_roles.id
          AND ministry_roles.church_ministry_id = church_ministries.id
          AND church_memberships.user_id = ministry_memberships.user_id
          AND church_ministries.id = ministry_memberships.church_ministry_id
        """
    )
    op.alter_column("user_ministry_roles", "ministry_membership_id", nullable=False)
    op.create_unique_constraint(
        "uq_user_ministry_roles_membership_role",
        "user_ministry_roles",
        ["ministry_membership_id", "ministry_role_id"],
    )
    op.create_table(
        "external_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("external_user_id", sa.String(128), nullable=False),
        sa.Column("username", sa.String(150), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "external_user_id"),
    )
    op.create_table(
        "registration_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("external_user_id", sa.String(128), nullable=False),
        sa.Column("external_username", sa.String(150), nullable=True),
        sa.Column("current_step", sa.String(32), nullable=False, server_default="church"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("registration_data", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "external_user_id"),
    )
    op.create_table(
        "consent_acceptances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("consent_acceptances")
    op.drop_table("registration_drafts")
    op.drop_table("external_accounts")
    op.drop_constraint(
        "uq_user_ministry_roles_membership_role", "user_ministry_roles", type_="unique"
    )
    op.drop_constraint(
        "fk_user_ministry_roles_ministry_membership_id",
        "user_ministry_roles",
        type_="foreignkey",
    )
    op.drop_column("user_ministry_roles", "ministry_membership_id")
    op.drop_table("ministry_memberships")
    op.drop_constraint(
        "fk_ministry_types_created_by_user_id_users", "ministry_types", type_="foreignkey"
    )
    op.drop_column("ministry_types", "created_by_user_id")
