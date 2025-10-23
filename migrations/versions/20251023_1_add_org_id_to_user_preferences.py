
"""
Add organization_id to user_preferences and create missing table/constraints if needed

Revision ID: 20251023_1
Revises: 20251021_101
Create Date: 2025-10-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20251023_1'
down_revision = '20251021_101'
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    try:
        return table_name in insp.get_table_names()
    except Exception:
        return False


def column_exists(table_name: str, column_name: str) -> bool:
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    insp = inspect(bind)
    try:
        return any(c['name'] == column_name for c in insp.get_columns(table_name))
    except Exception:
        return False


def constraint_exists(table: str, name: str) -> bool:
    try:
        bind = op.get_bind()
        insp = inspect(bind)
        for c in insp.get_foreign_keys(table):
            if c.get('name') == name:
                return True
    except Exception:
        pass
    return False


def upgrade():
    # Ensure user_preferences table exists with at least id and user_id
    if not table_exists('user_preferences'):
        op.create_table(
            'user_preferences',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('theme', sa.String(length=20), nullable=True),
            sa.Column('timezone', sa.String(length=64), nullable=True),
            sa.Column('dashboard_layout', sa.String(length=32), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.UniqueConstraint('user_id', name='uq_user_preferences_user_id'),
            sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='fk_user_preferences_user_id_user')
        )

    # Add organization_id column if missing
    if not column_exists('user_preferences', 'organization_id'):
        op.add_column('user_preferences', sa.Column('organization_id', sa.Integer(), nullable=True))
        # Backfill organization_id from user table where possible
        try:
            op.execute(
                """
                UPDATE user_preferences up
                SET organization_id = u.organization_id
                FROM "user" u
                WHERE up.user_id = u.id AND up.organization_id IS NULL
                """
            )
        except Exception:
            # Ignore if UPDATE fails (e.g., SQLite)
            pass
        # Set NOT NULL if all rows have value; otherwise leave nullable to avoid failures in prod
        # We cannot easily check row data portably here, so keep nullable=True for safety
        # Add FK if not present
        if not constraint_exists('user_preferences', 'fk_user_preferences_organization_id_organization'):
            try:
                with op.batch_alter_table('user_preferences') as batch_op:
                    batch_op.create_foreign_key(
                        'fk_user_preferences_organization_id_organization',
                        'organization',
                        ['organization_id'],
                        ['id']
                    )
            except Exception:
                # Best-effort; continue if FK creation fails
                pass


def downgrade():
    # Best-effort drop of organization_id
    if column_exists('user_preferences', 'organization_id'):
        try:
            with op.batch_alter_table('user_preferences') as batch_op:
                # Drop FK if it exists
                try:
                    batch_op.drop_constraint('fk_user_preferences_organization_id_organization', type_='foreignkey')
                except Exception:
                    pass
                batch_op.drop_column('organization_id')
        except Exception:
            pass
