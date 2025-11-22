"""0004 seed presets (guarded)

Revision ID: 0004_seed_presets
Revises: 0003_postgres_specific
Create Date: 2025-10-21 20:28:54.476996

"""
import os

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004_seed_presets'
down_revision = '0003_postgres_specific'
branch_labels = None
depends_on = None


def upgrade():
    # Guarded seeding: only when SEED_PRESETS=1
    if os.environ.get("SEED_PRESETS") != "1":
        print("   ℹ️ 0004_seed_presets skipped (SEED_PRESETS env not set to 1).")
        return

    bind = op.get_bind()
    dialect = bind.dialect.name

    # Seed roles (idempotent)
    roles = [
        ("organization_owner", "Organization Owner", True, True),
        ("manager", "Manager", True, True),
        ("member", "Member", True, True),
    ]

    if dialect == "postgresql":
        for key, name, is_active, is_system in roles:
            op.execute(
                sa.text(
                    """
                    INSERT INTO role (name, description, is_active, is_system_role)
                    VALUES (:n, :d, :a, :s)
                    ON CONFLICT (name) DO NOTHING
                    """
                ),
                {"n": key, "d": name, "a": True, "s": True},
            )
    else:
        # SQLite lacks ON CONFLICT for arbitrary keys; emulate
        for key, name, is_active, is_system in roles:
            exists = bind.execute(sa.text("SELECT 1 FROM role WHERE name = :n"), {"n": key}).fetchone()
            if not exists:
                bind.execute(
                    sa.text(
                        "INSERT INTO role (name, description, is_active, is_system_role) VALUES (:n, :d, :a, :s)"
                    ),
                    {"n": key, "d": name, "a": True, "s": True},
                )

    # Seed permissions (minimal examples)
    perms = [
        ("view_dashboard", "Access dashboard"),
        ("manage_inventory", "Create/update inventory"),
        ("manage_batches", "Create/update batches"),
    ]
    if dialect == "postgresql":
        for key, desc in perms:
            op.execute(
                sa.text(
                    "INSERT INTO permission (name, description, is_active, created_at)\n"
                    "VALUES (:n, :d, TRUE, CURRENT_TIMESTAMP)\n"
                    "ON CONFLICT (name) DO NOTHING"
                ),
                {"n": key, "d": desc},
            )
    else:
        for key, desc in perms:
            exists = bind.execute(sa.text("SELECT 1 FROM permission WHERE name = :n"), {"n": key}).fetchone()
            if not exists:
                bind.execute(
                    sa.text(
                        "INSERT INTO permission (name, description, is_active, created_at) VALUES (:n, :d, 1, CURRENT_TIMESTAMP)"
                    ),
                    {"n": key, "d": desc},
                )


def downgrade():
    # No-op: don't delete seeded presets on downgrade to avoid data loss
    # If required, implement safe deletes here.
    return
