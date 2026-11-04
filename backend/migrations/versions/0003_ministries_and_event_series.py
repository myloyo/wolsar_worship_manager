from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_ministries_and_event_series"
down_revision: str | None = "0002_add_churches"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ministry_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(150), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "church_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "church_id",
            sa.Integer(),
            sa.ForeignKey("churches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("access_level", sa.String(32), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("church_id", "user_id"),
    )
    op.create_table(
        "church_ministries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "church_id",
            sa.Integer(),
            sa.ForeignKey("churches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ministry_type_id",
            sa.Integer(),
            sa.ForeignKey("ministry_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("church_id", "ministry_type_id"),
    )
    op.create_table(
        "ministry_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "church_ministry_id",
            sa.Integer(),
            sa.ForeignKey("church_ministries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("church_ministry_id", "code"),
        sa.UniqueConstraint("church_ministry_id", "name"),
    )
    op.create_table(
        "user_ministry_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "church_membership_id",
            sa.Integer(),
            sa.ForeignKey("church_memberships.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ministry_role_id",
            sa.Integer(),
            sa.ForeignKey("ministry_roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("church_membership_id", "ministry_role_id"),
    )
    op.create_table(
        "event_series",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "church_ministry_id",
            sa.Integer(),
            sa.ForeignKey("church_ministries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_name", sa.String(150), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Europe/Saratov"),
        sa.Column("recurrence_rule", sa.String(500), nullable=True),
        sa.Column("repeats_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("additional_info", sa.Text(), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column("events", sa.Column("church_ministry_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_events_church_ministry_id_church_ministries",
        "events",
        "church_ministries",
        ["church_ministry_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column("events", sa.Column("event_series_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_events_event_series_id_event_series",
        "events",
        "event_series",
        ["event_series_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.add_column("events", sa.Column("additional_info", sa.Text(), nullable=True))
    op.create_table(
        "event_role_slots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "ministry_role_id",
            sa.Integer(),
            sa.ForeignKey("ministry_roles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("slot_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "user_ministry_role_id",
            sa.Integer(),
            sa.ForeignKey("user_ministry_roles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("confirmation_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", "ministry_role_id", "slot_number"),
    )
    op.add_column(
        "event_songs", sa.Column("position", sa.Integer(), nullable=False, server_default="0")
    )

    op.execute(
        """
        INSERT INTO churches (name, created_at, updated_at)
        VALUES ('Церковь «Слово Жизни», г. Саратов', now(), now())
        ON CONFLICT (name) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO ministry_types (code, name, created_at, updated_at)
        VALUES ('worship', 'Прославление', now(), now())
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE users
        SET church_id = (SELECT id FROM churches WHERE name = 'Церковь «Слово Жизни», г. Саратов')
        WHERE church_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE events
        SET church_id = (SELECT id FROM churches WHERE name = 'Церковь «Слово Жизни», г. Саратов')
        WHERE church_id IS NULL
        """
    )
    op.alter_column("users", "church_id", nullable=False)
    op.alter_column("events", "church_id", nullable=False)
    op.execute(
        """
        INSERT INTO church_ministries (church_id, ministry_type_id, created_at, updated_at)
        SELECT churches.id, ministry_types.id, now(), now()
        FROM churches CROSS JOIN ministry_types
        WHERE ministry_types.code = 'worship'
        ON CONFLICT (church_id, ministry_type_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO church_memberships (church_id, user_id, access_level, created_at, updated_at)
        SELECT church_id, id, system_role, now(), now() FROM users
        ON CONFLICT (church_id, user_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO ministry_roles (church_ministry_id, code, name, created_at, updated_at)
        SELECT church_ministries.id, roles.code, roles.name, now(), now()
        FROM church_ministries
        CROSS JOIN (VALUES
            ('lead_vocal', 'Ведущий вокал'),
            ('back_vocal', 'Бэк-вокал'),
            ('back_vocal_2', 'Бэк-вокал 2'),
            ('back_vocal_3', 'Бэк-вокал 3'),
            ('drums', 'Барабаны'),
            ('bass', 'Бас-гитара'),
            ('electric_guitar', 'Электрогитара'),
            ('electric_guitar_2', 'Электрогитара 2'),
            ('acoustic_guitar', 'Акустическая гитара'),
            ('keys', 'Клавиши'),
            ('violin', 'Скрипка'),
            ('sound', 'Звук'),
            ('sound_2', 'Звук 2')
        ) AS roles(code, name)
        ON CONFLICT (church_ministry_id, code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO ministry_roles (church_ministry_id, code, name, created_at, updated_at)
        SELECT church_ministries.id, user_worship_assignments.worship_role,
               user_worship_assignments.worship_role, now(), now()
        FROM user_worship_assignments
        JOIN users ON users.id = user_worship_assignments.user_id
        JOIN church_ministries ON church_ministries.church_id = users.church_id
        JOIN ministry_types ON ministry_types.id = church_ministries.ministry_type_id
        WHERE ministry_types.code = 'worship'
        ON CONFLICT (church_ministry_id, code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO user_ministry_roles (church_membership_id, ministry_role_id, created_at)
        SELECT church_memberships.id, ministry_roles.id, now()
        FROM user_worship_assignments
        JOIN users ON users.id = user_worship_assignments.user_id
        JOIN church_memberships ON church_memberships.user_id = users.id
                                  AND church_memberships.church_id = users.church_id
        JOIN church_ministries ON church_ministries.church_id = users.church_id
        JOIN ministry_types ON ministry_types.id = church_ministries.ministry_type_id
                            AND ministry_types.code = 'worship'
        JOIN ministry_roles ON ministry_roles.church_ministry_id = church_ministries.id
                            AND ministry_roles.code = user_worship_assignments.worship_role
        ON CONFLICT (church_membership_id, ministry_role_id) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE events
        SET church_ministry_id = church_ministries.id
        FROM church_ministries
        JOIN ministry_types ON ministry_types.id = church_ministries.ministry_type_id
                            AND ministry_types.code = 'worship'
        WHERE events.church_id = church_ministries.church_id
          AND events.church_ministry_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("event_songs", "position")
    op.drop_table("event_role_slots")
    op.drop_column("events", "additional_info")
    op.drop_constraint("fk_events_event_series_id_event_series", "events", type_="foreignkey")
    op.drop_column("events", "event_series_id")
    op.drop_constraint(
        "fk_events_church_ministry_id_church_ministries", "events", type_="foreignkey"
    )
    op.drop_column("events", "church_ministry_id")
    op.drop_table("event_series")
    op.drop_table("user_ministry_roles")
    op.drop_table("ministry_roles")
    op.drop_table("church_ministries")
    op.drop_table("church_memberships")
    op.drop_table("ministry_types")
