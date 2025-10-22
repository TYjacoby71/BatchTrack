
"""0007 final nullability constraints

Revision ID: 0007_final_nullability
Revises: 0006_schema_alignment
Create Date: 2025-01-22 16:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0007_final_nullability'
down_revision = '0006_schema_alignment'
branch_labels = None
depends_on = None


def upgrade():
    # Harden boolean defaults to be portable (sa.true()/sa.false()) and not null where desired
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Backfill first
    op.execute(sa.text('UPDATE "user" SET is_active = false WHERE is_active IS NULL'))
    op.execute(sa.text('UPDATE role SET is_active = false WHERE is_active IS NULL'))
    op.execute(sa.text('UPDATE inventory_item SET is_active = true WHERE is_active IS NULL'))
    op.execute(sa.text('UPDATE inventory_item SET is_archived = false WHERE is_archived IS NULL'))
    op.execute(sa.text('UPDATE feature_flag SET enabled = false WHERE enabled IS NULL'))

    if dialect == 'sqlite':
        # Use batch mode for SQLite to emulate ALTER COLUMN
        with op.batch_alter_table('user') as batch_op:
            batch_op.alter_column('is_active', existing_type=sa.Boolean(), server_default=sa.false(), nullable=False)
        with op.batch_alter_table('role') as batch_op:
            batch_op.alter_column('is_active', existing_type=sa.Boolean(), server_default=sa.false(), nullable=False)
        with op.batch_alter_table('inventory_item') as batch_op:
            batch_op.alter_column('is_active', existing_type=sa.Boolean(), server_default=sa.true(), nullable=False)
            batch_op.alter_column('is_archived', existing_type=sa.Boolean(), server_default=sa.false(), nullable=False)
        with op.batch_alter_table('feature_flag') as batch_op:
            batch_op.alter_column('enabled', existing_type=sa.Boolean(), server_default=sa.false(), nullable=False)
    else:
        op.alter_column('user', 'is_active', existing_type=sa.Boolean(), server_default=sa.false(), nullable=False)
        op.alter_column('role', 'is_active', existing_type=sa.Boolean(), server_default=sa.false(), nullable=False)
        op.alter_column('inventory_item', 'is_active', existing_type=sa.Boolean(), server_default=sa.true(), nullable=False)
        op.alter_column('inventory_item', 'is_archived', existing_type=sa.Boolean(), server_default=sa.false(), nullable=False)
        op.alter_column('feature_flag', 'enabled', existing_type=sa.Boolean(), server_default=sa.false(), nullable=False)


def downgrade():
    # Don't reverse the constraint changes - leave them hardened
    # This prevents the back-and-forth nullable changes that cause issues
    pass
