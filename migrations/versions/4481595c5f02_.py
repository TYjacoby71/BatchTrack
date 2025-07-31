"""empty message

Revision ID: 4481595c5f02
Revises: 
Create Date: 2025-07-31 04:17:39.076548

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4481595c5f02'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create base tables first (no dependencies)
    op.create_table('organization',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('timezone', sa.String(length=50), nullable=True),
    sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
    sa.Column('subscription_tier', sa.String(length=50), nullable=True),
    sa.Column('subscription_status', sa.String(length=50), nullable=True),
    sa.Column('subscription_start_date', sa.DateTime(), nullable=True),
    sa.Column('subscription_end_date', sa.DateTime(), nullable=True),
    sa.Column('billing_cycle', sa.String(length=20), nullable=True),
    sa.Column('subscription_item_id', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('stripe_customer_id')
    )

    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=80), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=False),
    sa.Column('password_hash', sa.String(length=120), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('organization_id', sa.Integer(), nullable=True),
    sa.Column('user_type', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('email_verified', sa.Boolean(), nullable=True),
    sa.Column('email_verification_token', sa.String(length=255), nullable=True),
    sa.Column('password_reset_token', sa.String(length=255), nullable=True),
    sa.Column('password_reset_expires', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('username')
    )

    # Create other base tables
    op.create_table('ingredient_category',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('density', sa.Float(), nullable=True),
    sa.Column('organization_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('permission',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )

    op.create_table('role',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('organization_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('subscription_tier',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('display_name', sa.String(length=100), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('max_users', sa.Integer(), nullable=True),
    sa.Column('max_organizations', sa.Integer(), nullable=True),
    sa.Column('stripe_price_id_monthly', sa.String(length=255), nullable=True),
    sa.Column('stripe_price_id_yearly', sa.String(length=255), nullable=True),
    sa.Column('price_monthly', sa.Float(), nullable=True),
    sa.Column('price_yearly', sa.Float(), nullable=True),
    sa.Column('features', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )

    op.create_table('tag',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('color', sa.String(length=7), nullable=True),
    sa.Column('organization_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('unit',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('symbol', sa.String(length=10), nullable=False),
    sa.Column('unit_type', sa.String(length=20), nullable=False),
    sa.Column('is_base_unit', sa.Boolean(), nullable=True),
    sa.Column('conversion_factor', sa.Float(), nullable=True),
    sa.Column('organization_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # Create intermediate tables that depend on the above
    op.create_table('developer_permission',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )

    op.create_table('developer_role',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )

    op.create_table('inventory_item',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('quantity', sa.Float(), nullable=False),
    sa.Column('unit', sa.String(length=50), nullable=False),
    sa.Column('cost_per_unit', sa.Float(), nullable=True),
    sa.Column('low_stock_threshold', sa.Float(), nullable=True),
    sa.Column('category_id', sa.Integer(), nullable=True),
    sa.Column('organization_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('supplier', sa.String(length=100), nullable=True),
    sa.Column('purchase_date', sa.Date(), nullable=True),
    sa.Column('expiration_date', sa.Date(), nullable=True),
    sa.Column('batch_code', sa.String(length=50), nullable=True),
    sa.Column('storage_location', sa.String(length=100), nullable=True),
    sa.Column('fifo_code', sa.String(length=20), nullable=True),
    sa.Column('item_type', sa.String(length=20), nullable=True),
    sa.ForeignKeyConstraint(['category_id'], ['ingredient_category.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('recipe',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('base_yield', sa.Float(), nullable=True),
    sa.Column('yield_unit', sa.String(length=50), nullable=True),
    sa.Column('organization_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('instructions', sa.Text(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('tags', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('role_permission',
    sa.Column('role_id', sa.Integer(), nullable=False),
    sa.Column('permission_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['permission_id'], ['permission.id'], ),
    sa.ForeignKeyConstraint(['role_id'], ['role.id'], ),
    sa.PrimaryKeyConstraint('role_id', 'permission_id')
    )

    op.create_table('user_preferences',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('theme', sa.String(length=20), nullable=True),
    sa.Column('timezone', sa.String(length=50), nullable=True),
    sa.Column('date_format', sa.String(length=20), nullable=True),
    sa.Column('email_notifications', sa.Boolean(), nullable=True),
    sa.Column('dashboard_layout', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )

    op.create_table('user_role_assignment',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('role_id', sa.Integer(), nullable=False),
    sa.Column('assigned_at', sa.DateTime(), nullable=True),
    sa.Column('assigned_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['assigned_by'], ['user.id'], ),
    sa.ForeignKeyConstraint(['role_id'], ['role.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # Create tables that depend on recipe and inventory_item
    op.create_table('product',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('base_recipe_id', sa.Integer(), nullable=True),
    sa.Column('organization_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('category', sa.String(length=50), nullable=True),
    sa.Column('tags', sa.Text(), nullable=True),
    sa.Column('image_url', sa.String(length=255), nullable=True),
    sa.ForeignKeyConstraint(['base_recipe_id'], ['recipe.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('recipe_ingredient',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('recipe_id', sa.Integer(), nullable=False),
    sa.Column('inventory_item_id', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Float(), nullable=False),
    sa.Column('unit', sa.String(length=50), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('order_index', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id'], ),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # Create product related tables
    op.create_table('product_sku',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('sku_code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('size', sa.Float(), nullable=True),
    sa.Column('size_unit', sa.String(length=20), nullable=True),
    sa.Column('price', sa.Float(), nullable=True),
    sa.Column('cost', sa.Float(), nullable=True),
    sa.Column('inventory_item_id', sa.Integer(), nullable=True),
    sa.Column('organization_id', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sku_code')
    )

    op.create_table('product_variant',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('recipe_id', sa.Integer(), nullable=True),
    sa.Column('price_modifier', sa.Float(), nullable=True),
    sa.Column('cost_modifier', sa.Float(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], ),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # Now create batch table (depends on user, organization, recipe, product_sku)
    op.create_table('batch',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('recipe_id', sa.Integer(), nullable=False),
    sa.Column('label_code', sa.String(length=32), nullable=True),
    sa.Column('batch_type', sa.String(length=32), nullable=False),
    sa.Column('projected_yield', sa.Float(), nullable=True),
    sa.Column('projected_yield_unit', sa.String(length=50), nullable=True),
    sa.Column('sku_id', sa.Integer(), nullable=True),
    sa.Column('final_quantity', sa.Float(), nullable=True),
    sa.Column('output_unit', sa.String(length=50), nullable=True),
    sa.Column('scale', sa.Float(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
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
    sa.Column('inventory_credited', sa.Boolean(), nullable=True),
    sa.Column('is_perishable', sa.Boolean(), nullable=True),
    sa.Column('shelf_life_days', sa.Integer(), nullable=True),
    sa.Column('expiration_date', sa.DateTime(), nullable=True),
    sa.Column('remaining_quantity', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id'], ),
    sa.ForeignKeyConstraint(['sku_id'], ['product_sku.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('label_code')
    )

    # Create remaining tables that depend on batch or other complex dependencies
    op.create_table('batch_ingredient',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('inventory_item_id', sa.Integer(), nullable=False),
    sa.Column('quantity_used', sa.Float(), nullable=False),
    sa.Column('unit', sa.String(length=50), nullable=False),
    sa.Column('cost_per_unit', sa.Float(), nullable=True),
    sa.Column('total_cost', sa.Float(), nullable=True),
    sa.Column('fifo_deduction_log', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['batch_id'], ['batch.id'], ),
    sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('batch_container',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('container_name', sa.String(length=100), nullable=False),
    sa.Column('container_size', sa.Float(), nullable=False),
    sa.Column('container_unit', sa.String(length=20), nullable=False),
    sa.Column('quantity_filled', sa.Float(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('label_printed', sa.Boolean(), nullable=True),
    sa.Column('qr_code', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['batch_id'], ['batch.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('batch_inventory_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('inventory_item_id', sa.Integer(), nullable=False),
    sa.Column('quantity_before', sa.Float(), nullable=False),
    sa.Column('quantity_used', sa.Float(), nullable=False),
    sa.Column('quantity_after', sa.Float(), nullable=False),
    sa.Column('unit', sa.String(length=50), nullable=False),
    sa.Column('cost_per_unit', sa.Float(), nullable=True),
    sa.Column('total_cost', sa.Float(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['batch_id'], ['batch.id'], ),
    sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('batch_timer',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('timer_name', sa.String(length=100), nullable=False),
    sa.Column('duration_minutes', sa.Integer(), nullable=False),
    sa.Column('start_time', sa.DateTime(), nullable=True),
    sa.Column('end_time', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['batch_id'], ['batch.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('billing_snapshot',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('organization_id', sa.Integer(), nullable=False),
    sa.Column('user_count', sa.Integer(), nullable=False),
    sa.Column('batch_count', sa.Integer(), nullable=False),
    sa.Column('recipe_count', sa.Integer(), nullable=False),
    sa.Column('inventory_item_count', sa.Integer(), nullable=False),
    sa.Column('snapshot_date', sa.DateTime(), nullable=False),
    sa.Column('billing_period_start', sa.DateTime(), nullable=True),
    sa.Column('billing_period_end', sa.DateTime(), nullable=True),
    sa.Column('tier_at_snapshot', sa.String(length=50), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('conversion_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('from_amount', sa.Float(), nullable=False),
    sa.Column('from_unit', sa.String(length=50), nullable=False),
    sa.Column('to_amount', sa.Float(), nullable=False),
    sa.Column('to_unit', sa.String(length=50), nullable=False),
    sa.Column('conversion_factor', sa.Float(), nullable=False),
    sa.Column('category_density', sa.Float(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('organization_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('custom_unit_mapping',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ingredient_id', sa.Integer(), nullable=False),
    sa.Column('from_unit', sa.String(length=50), nullable=False),
    sa.Column('to_unit', sa.String(length=50), nullable=False),
    sa.Column('conversion_factor', sa.Float(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('organization_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['ingredient_id'], ['inventory_item.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('extra_batch_container',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('container_name', sa.String(length=100), nullable=False),
    sa.Column('container_size', sa.Float(), nullable=False),
    sa.Column('container_unit', sa.String(length=20), nullable=False),
    sa.Column('quantity_filled', sa.Float(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['batch_id'], ['batch.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('extra_batch_ingredient',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('inventory_item_id', sa.Integer(), nullable=False),
    sa.Column('quantity_used', sa.Float(), nullable=False),
    sa.Column('unit', sa.String(length=50), nullable=False),
    sa.Column('cost_per_unit', sa.Float(), nullable=True),
    sa.Column('total_cost', sa.Float(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('added_at', sa.DateTime(), nullable=True),
    sa.Column('added_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['added_by'], ['user.id'], ),
    sa.ForeignKeyConstraint(['batch_id'], ['batch.id'], ),
    sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('inventory_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('inventory_item_id', sa.Integer(), nullable=False),
    sa.Column('change_type', sa.String(length=50), nullable=False),
    sa.Column('quantity_before', sa.Float(), nullable=False),
    sa.Column('quantity_change', sa.Float(), nullable=False),
    sa.Column('quantity_after', sa.Float(), nullable=False),
    sa.Column('unit', sa.String(length=50), nullable=False),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('batch_id', sa.Integer(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['batch_id'], ['batch.id'], ),
    sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('organization_stats',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('organization_id', sa.Integer(), nullable=False),
    sa.Column('total_batches', sa.Integer(), nullable=True),
    sa.Column('total_recipes', sa.Integer(), nullable=True),
    sa.Column('total_inventory_items', sa.Integer(), nullable=True),
    sa.Column('total_users', sa.Integer(), nullable=True),
    sa.Column('avg_batch_cost', sa.Float(), nullable=True),
    sa.Column('total_production_value', sa.Float(), nullable=True),
    sa.Column('last_batch_date', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id')
    )

    op.create_table('pricing_snapshot',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('inventory_item_id', sa.Integer(), nullable=False),
    sa.Column('cost_per_unit_at_time', sa.Float(), nullable=False),
    sa.Column('quantity_used', sa.Float(), nullable=False),
    sa.Column('total_cost', sa.Float(), nullable=False),
    sa.Column('snapshot_date', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['batch_id'], ['batch.id'], ),
    sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('product_sku_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sku_id', sa.Integer(), nullable=False),
    sa.Column('change_type', sa.String(length=50), nullable=False),
    sa.Column('quantity_before', sa.Float(), nullable=True),
    sa.Column('quantity_change', sa.Float(), nullable=True),
    sa.Column('quantity_after', sa.Float(), nullable=True),
    sa.Column('unit', sa.String(length=50), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('batch_id', sa.Integer(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['batch_id'], ['batch.id'], ),
    sa.ForeignKeyConstraint(['sku_id'], ['product_sku.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('reservation',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('inventory_item_id', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Float(), nullable=False),
    sa.Column('unit', sa.String(length=50), nullable=False),
    sa.Column('reservation_type', sa.String(length=50), nullable=False),
    sa.Column('reference_id', sa.String(length=100), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('organization_id', sa.Integer(), nullable=True),
    sa.Column('batch_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['batch_id'], ['batch.id'], ),
    sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('user_stats',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('total_batches_created', sa.Integer(), nullable=True),
    sa.Column('total_recipes_created', sa.Integer(), nullable=True),
    sa.Column('last_login', sa.DateTime(), nullable=True),
    sa.Column('last_batch_date', sa.DateTime(), nullable=True),
    sa.Column('preferred_units', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )


def downgrade():
    # Drop tables in reverse dependency order
    op.drop_table('user_stats')
    op.drop_table('reservation')
    op.drop_table('product_sku_history')
    op.drop_table('pricing_snapshot')
    op.drop_table('organization_stats')
    op.drop_table('inventory_history')
    op.drop_table('extra_batch_ingredient')
    op.drop_table('extra_batch_container')
    op.drop_table('custom_unit_mapping')
    op.drop_table('conversion_log')
    op.drop_table('billing_snapshot')
    op.drop_table('batch_timer')
    op.drop_table('batch_inventory_log')
    op.drop_table('batch_container')
    op.drop_table('batch_ingredient')
    op.drop_table('batch')
    op.drop_table('product_variant')
    op.drop_table('product_sku')
    op.drop_table('recipe_ingredient')
    op.drop_table('product')
    op.drop_table('user_role_assignment')
    op.drop_table('user_preferences')
    op.drop_table('role_permission')
    op.drop_table('recipe')
    op.drop_table('inventory_item')
    op.drop_table('developer_role')
    op.drop_table('developer_permission')
    op.drop_table('unit')
    op.drop_table('tag')
    op.drop_table('subscription_tier')
    op.drop_table('role')
    op.drop_table('permission')
    op.drop_table('ingredient_category')
    op.drop_table('user')
    op.drop_table('organization')