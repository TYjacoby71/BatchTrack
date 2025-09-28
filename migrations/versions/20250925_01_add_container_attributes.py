"""
Add container structured attributes to inventory_item and global_item

Revision ID: 20250925_01_add_container_attributes
Revises: 20250923_04
Create Date: 2025-09-25 00:00:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250925_01_add_container_attributes'
down_revision = '20250923_04'
branch_labels = None
depends_on = None


def upgrade():
    # inventory_item: add container_material and container_type
    with op.batch_alter_table('inventory_item') as batch_op:
        batch_op.add_column(sa.Column('container_material', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('container_type', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('container_style', sa.String(length=64), nullable=True))

    # global_item: add container_material and container_type
    with op.batch_alter_table('global_item') as batch_op:
        batch_op.add_column(sa.Column('container_material', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('container_type', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('container_style', sa.String(length=64), nullable=True))


def downgrade():
    # global_item: drop container_material and container_type
    try:
        with op.batch_alter_table('global_item') as batch_op:
            batch_op.drop_column('container_style')
            batch_op.drop_column('container_type')
            batch_op.drop_column('container_material')
    except Exception:
        pass

    # inventory_item: drop container_material and container_type
    try:
        with op.batch_alter_table('inventory_item') as batch_op:
            batch_op.drop_column('container_style')
            batch_op.drop_column('container_type')
            batch_op.drop_column('container_material')
    except Exception:
        pass

