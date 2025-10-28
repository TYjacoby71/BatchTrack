"""rename container_shape to container_type

Revision ID: 0004_rename_shape
Revises: 0003_postgres_specific
Create Date: 2025-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004_rename_shape'
down_revision = '0003_postgres_specific'
branch_labels = None
depends_on = None


def upgrade():
    """Rename container_shape to container_type in inventory_item table"""
    # Rename the column
    with op.batch_alter_table('inventory_item', schema=None) as batch_op:
        batch_op.alter_column('container_shape',
                              new_column_name='container_type',
                              existing_type=sa.String(length=64),
                              existing_nullable=True)


def downgrade():
    """Rename container_type back to container_shape"""
    with op.batch_alter_table('inventory_item', schema=None) as batch_op:
        batch_op.alter_column('container_type',
                              new_column_name='container_shape',
                              existing_type=sa.String(length=64),
                              existing_nullable=True)
