"""Add consumables tables for recipes and batches

Revision ID: 2025090502
Revises: 20250906_01
Create Date: 2025-09-05 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '2025090502'
down_revision = '20250906_01'
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists"""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade():
    """Add consumables tables for recipes and batches"""
    print("=== Adding consumables tables ===")

    # Create recipe_consumable table if it doesn't exist
    if not table_exists('recipe_consumable'):
        print("   Creating recipe_consumable table...")
        op.create_table(
            'recipe_consumable',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('recipe_id', sa.Integer(), nullable=False),
            sa.Column('inventory_item_id', sa.Integer(), nullable=False),
            sa.Column('quantity', sa.Float(), nullable=False),
            sa.Column('unit', sa.String(32), nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('order_position', sa.Integer(), nullable=False, default=0),
            sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id']),
            sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
            sa.PrimaryKeyConstraint('id')
        )
        print("   ✅ Created recipe_consumable table")
    else:
        print("   ✅ recipe_consumable table already exists - skipping")

    # Create batch_consumable table if it doesn't exist
    if not table_exists('batch_consumable'):
        print("   Creating batch_consumable table...")
        op.create_table(
            'batch_consumable',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('batch_id', sa.Integer(), nullable=False),
            sa.Column('inventory_item_id', sa.Integer(), nullable=False),
            sa.Column('quantity', sa.Float(), nullable=False),
            sa.Column('unit', sa.String(32), nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('order_position', sa.Integer(), nullable=False, default=0),
            sa.ForeignKeyConstraint(['batch_id'], ['batch.id']),
            sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
            sa.PrimaryKeyConstraint('id')
        )
        print("   ✅ Created batch_consumable table")
    else:
        print("   ✅ batch_consumable table already exists - skipping")

    # Create extra_batch_consumable table if it doesn't exist
    if not table_exists('extra_batch_consumable'):
        print("   Creating extra_batch_consumable table...")
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
        print("   ✅ Created extra_batch_consumable table")
    else:
        print("   ✅ extra_batch_consumable table already exists - skipping")

    print("✅ Consumables migration completed successfully")


def downgrade():
    """Remove consumables tables"""
    print("=== Removing consumables tables ===")

    # Drop tables in reverse order if they exist
    if table_exists('extra_batch_consumable'):
        print("   Dropping extra_batch_consumable table...")
        op.drop_table('extra_batch_consumable')
        print("   ✅ Dropped extra_batch_consumable table")
    else:
        print("   ✅ extra_batch_consumable table does not exist - skipping")

    if table_exists('batch_consumable'):
        print("   Dropping batch_consumable table...")
        op.drop_table('batch_consumable')
        print("   ✅ Dropped batch_consumable table")
    else:
        print("   ✅ batch_consumable table does not exist - skipping")

    if table_exists('recipe_consumable'):
        print("   Dropping recipe_consumable table...")
        op.drop_table('recipe_consumable')
        print("   ✅ Dropped recipe_consumable table")
    else:
        print("   ✅ recipe_consumable table does not exist - skipping")

    print("✅ Consumables downgrade completed successfully")