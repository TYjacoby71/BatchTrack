"""Production bootstrap 0003 - recipe, batch, consumables, timers, reservations

Revision ID: prod_0003_recipe_batch
Revises: prod_0002_inventory_products
Create Date: 2025-09-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'prod_0003_recipe_batch'
down_revision = 'prod_0002_inventory_products'
branch_labels = ('production_bootstrap',)
depends_on = None


def upgrade():
    # Recipes
    op.create_table(
        'recipe',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('label_prefix', sa.String(length=8), nullable=True),
        sa.Column('qr_image', sa.String(length=128), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('is_locked', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('predicted_yield', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('predicted_yield_unit', sa.String(length=50), nullable=True, server_default='oz'),
        sa.Column('allowed_containers', sa.PickleType(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['parent_id'], ['recipe.id']),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
    )

    op.create_table(
        'recipe_ingredient',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('recipe_id', sa.Integer(), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=32), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('order_position', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id']),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
    )

    op.create_table(
        'recipe_consumable',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('recipe_id', sa.Integer(), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=32), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('order_position', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id']),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
    )

    # Batches and related
    op.create_table(
        'batch',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('recipe_id', sa.Integer(), nullable=False),
        sa.Column('label_code', sa.String(length=32), nullable=True, unique=True),
        sa.Column('batch_type', sa.String(length=32), nullable=False),
        sa.Column('projected_yield', sa.Float(), nullable=True),
        sa.Column('projected_yield_unit', sa.String(length=50), nullable=True),
        sa.Column('sku_id', sa.Integer(), nullable=True),
        sa.Column('final_quantity', sa.Float(), nullable=True),
        sa.Column('output_unit', sa.String(length=50), nullable=True),
        sa.Column('scale', sa.Float(), nullable=True, server_default='1.0'),
        sa.Column('status', sa.String(length=50), nullable=True, server_default='in_progress'),
        sa.Column('status_reason', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column('total_cost', sa.Float(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('failed_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('inventory_credited', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('is_perishable', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('shelf_life_days', sa.Integer(), nullable=True),
        sa.Column('expiration_date', sa.DateTime(), nullable=True),
        sa.Column('remaining_quantity', sa.Float(), nullable=True),
        sa.Column('cost_method', sa.String(length=16), nullable=True),
        sa.Column('cost_method_locked_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id']),
        sa.ForeignKeyConstraint(['sku_id'], ['product_sku.id']),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
    )

    # Now that batch exists, add the deferred FK from product_sku.batch_id -> batch.id
    try:
        op.create_foreign_key('fk_product_sku_batch_id', 'product_sku', 'batch', ['batch_id'], ['id'])
    except Exception:
        # If already present or in SQLite no-op contexts
        pass

    op.create_index('ix_user_organization_id', 'user', ['organization_id'])

    op.create_table(
        'batch_ingredient',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('quantity_used', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=32), nullable=False),
        sa.Column('cost_per_unit', sa.Float(), nullable=True),
        sa.Column('total_cost', sa.Float(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['batch.id']),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
    )

    op.create_table(
        'batch_container',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('container_id', sa.Integer(), nullable=False),
        sa.Column('container_quantity', sa.Integer(), nullable=False),
        sa.Column('quantity_used', sa.Integer(), nullable=False),
        sa.Column('fill_quantity', sa.Float(), nullable=True),
        sa.Column('fill_unit', sa.String(length=32), nullable=True),
        sa.Column('cost_each', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['batch.id']),
        sa.ForeignKeyConstraint(['container_id'], ['inventory_item.id']),
    )

    op.create_table(
        'extra_batch_ingredient',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('quantity_used', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=32), nullable=False),
        sa.Column('cost_per_unit', sa.Float(), nullable=True),
        sa.Column('total_cost', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['batch.id']),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
    )

    op.create_table(
        'batch_consumable',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('quantity_used', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=32), nullable=False),
        sa.Column('cost_per_unit', sa.Float(), nullable=True),
        sa.Column('total_cost', sa.Float(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['batch.id']),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
    )

    op.create_table(
        'extra_batch_consumable',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('quantity_used', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=32), nullable=False),
        sa.Column('cost_per_unit', sa.Float(), nullable=True),
        sa.Column('total_cost', sa.Float(), nullable=True),
        sa.Column('reason', sa.String(length=20), nullable=False, server_default='extra_use'),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['batch.id']),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
    )

    op.create_table(
        'batch_timer',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('batch_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=True, server_default='active'),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['batch.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
    )

    # Reservations
    op.create_table(
        'reservation',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_id', sa.String(length=128), nullable=False),
        sa.Column('reservation_id', sa.String(length=128), nullable=True),
        sa.Column('product_item_id', sa.Integer(), nullable=False),
        sa.Column('reserved_item_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=32), nullable=False),
        sa.Column('unit_cost', sa.Float(), nullable=True),
        sa.Column('sale_price', sa.Float(), nullable=True),
        sa.Column('customer', sa.String(length=128), nullable=True),
        sa.Column('source_fifo_id', sa.Integer(), nullable=True),
        sa.Column('source_batch_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=True, server_default='active'),
        sa.Column('source', sa.String(length=64), nullable=True, server_default='shopify'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('released_at', sa.DateTime(), nullable=True),
        sa.Column('converted_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['product_item_id'], ['inventory_item.id']),
        sa.ForeignKeyConstraint(['reserved_item_id'], ['inventory_item.id']),
        sa.ForeignKeyConstraint(['source_batch_id'], ['batch.id']),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
    )
    op.create_index('idx_order_status', 'reservation', ['order_id', 'status'])
    op.create_index('idx_reserved_item_status', 'reservation', ['reserved_item_id', 'status'])
    op.create_index('idx_expires_at', 'reservation', ['expires_at'])


def downgrade():
    op.drop_index('idx_expires_at', table_name='reservation')
    op.drop_index('idx_reserved_item_status', table_name='reservation')
    op.drop_index('idx_order_status', table_name='reservation')
    op.drop_table('reservation')
    op.drop_table('batch_timer')
    op.drop_table('extra_batch_consumable')
    op.drop_table('batch_consumable')
    op.drop_table('extra_batch_ingredient')
    op.drop_table('batch_container')
    op.drop_table('batch_ingredient')
    op.drop_index('ix_user_organization_id', table_name='user')
    op.drop_table('batch')
    op.drop_table('recipe_consumable')
    op.drop_table('recipe_ingredient')
    op.drop_table('recipe')

