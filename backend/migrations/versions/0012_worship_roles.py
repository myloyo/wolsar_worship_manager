from alembic import op

revision = "0012_worship_roles"
down_revision = "0011_membership_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO ministry_roles (church_ministry_id, code, name, created_at, updated_at)
        SELECT team.id, role.code, role.name, now(), now()
        FROM church_ministries team
        JOIN ministry_types kind ON kind.id = team.ministry_type_id
        CROSS JOIN (VALUES
('lead_vocal', 'Ведущий вокал'),
('back_vocal', 'Бэк-вокал'),
('acoustic_guitar', 'Акустическая гитара'),
('electric_guitar', 'Электрогитара'),
('bass', 'Бас-гитара'),
('drums', 'Барабаны'),
('keys', 'Клавиши'),
('violin', 'Скрипка'),
('sound', 'Звукорежиссёр'),
('dance', 'Танцы')
        ) AS role(code, name)
        WHERE (kind.code = 'worship' OR lower(kind.name) = 'прославление')
          AND NOT EXISTS (
              SELECT 1 FROM ministry_roles existing
              WHERE existing.church_ministry_id = team.id
                AND (existing.code = role.code OR lower(existing.name) = lower(role.name))
          )
        ON CONFLICT (church_ministry_id, code) DO NOTHING
    """)


def downgrade() -> None:
    # Preserve roles and assignments already used by the congregation.
    pass
