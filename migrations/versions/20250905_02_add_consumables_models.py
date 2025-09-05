"""
add consumables tables for recipes and batches

Revision ID: 2025090502
Revises: 2025090501
Create Date: 2025-09-05
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2025090502'
down_revision = '2025090501'
branch_labels = None
depends_on = None


def upgrade():
    # recipe_consumable table
    op.create_table(
        'recipe_consumable',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('recipe_id', sa.Integer(), sa.ForeignKey('recipe.id'), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), sa.ForeignKey('inventory_item.id'), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=32), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('order_position', sa.Integer(), nullable=True, server_default='0')
    )

    # batch_consumable table
    op.create_table(
        'batch_consumable',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('batch_id', sa.Integer(), sa.ForeignKey('batch.id'), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), sa.ForeignKey('inventory_item.id'), nullable=False),
        sa.Column('quantity_used', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=32), nullable=False),
        sa.Column('cost_per_unit', sa.Float(), nullable=True),
        sa.Column('total_cost', sa.Float(), nullable=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organization.id'), nullable=True)
    )

    # extra_batch_consumable table
    op.create_table(
        'extra_batch_consumable',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('batch_id', sa.Integer(), sa.ForeignKey('batch.id'), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), sa.ForeignKey('inventory_item.id'), nullable=False),
        sa.Column('quantity_used', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=32), nullable=False),
        sa.Column('cost_per_unit', sa.Float(), nullable=True),
        sa.Column('total_cost', sa.Float(), nullable=True),
        sa.Column('reason', sa.String(length=20), nullable=False, server_default='extra_use'),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organization.id'), nullable=True)
    )


def downgrade():
    op.drop_table('extra_batch_consumable')
    op.drop_table('batch_consumable')
    op.drop_table('recipe_consumable')

