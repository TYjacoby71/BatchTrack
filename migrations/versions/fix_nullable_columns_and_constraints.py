
"""fix nullable columns and add constraints

Revision ID: fix_nullable_constraints
Revises: add_missing_timestamps
Create Date: 2025-08-01 00:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = 'fix_nullable_constraints'
down_revision = 'add_missing_timestamps'
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists"""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    """Fix nullable columns and add missing constraints"""
    print("=== Fixing nullable columns and adding constraints ===")
    
    # Fix columns that should NOT be nullable and add defaults for failed columns
    
    # Fix inventory_item
    if column_exists('inventory_item', 'type'):
        op.execute("UPDATE inventory_item SET type = 'ingredient' WHERE type IS NULL")
        op.alter_column('inventory_item', 'type', nullable=False, server_default='ingredient')
    
    if column_exists('inventory_item', 'is_active'):
        op.execute("UPDATE inventory_item SET is_active = true WHERE is_active IS NULL")
        op.alter_column('inventory_item', 'is_active', nullable=False, server_default='true')
    
    # Fix user table
    if column_exists('user', 'timezone'):
        op.execute("UPDATE \"user\" SET timezone = 'UTC' WHERE timezone IS NULL")
        op.alter_column('user', 'timezone', nullable=False, server_default='UTC')
    
    # Fix reservation table
    if column_exists('reservation', 'source'):
        op.execute("UPDATE reservation SET source = 'manual' WHERE source IS NULL")
        op.alter_column('reservation', 'source', nullable=False, server_default='manual')
    
    if column_exists('reservation', 'status'):
        op.execute("UPDATE reservation SET status = 'active' WHERE status IS NULL")
        op.alter_column('reservation', 'status', nullable=False, server_default='active')
    
    # Fix batch_timer
    if column_exists('batch_timer', 'status'):
        op.execute("UPDATE batch_timer SET status = 'active' WHERE status IS NULL")
        op.alter_column('batch_timer', 'status', nullable=False, server_default='active')
    
    # Fix extra_batch_container
    if column_exists('extra_batch_container', 'reason'):
        op.execute("UPDATE extra_batch_container SET reason = 'extra_yield' WHERE reason IS NULL")
        op.alter_column('extra_batch_container', 'reason', nullable=False, server_default='extra_yield')
    
    # Fix recipe
    if column_exists('recipe', 'predicted_yield_unit'):
        op.execute("UPDATE recipe SET predicted_yield_unit = 'oz' WHERE predicted_yield_unit IS NULL")
        op.alter_column('recipe', 'predicted_yield_unit', nullable=False, server_default='oz')
    
    # Fix developer_role
    if column_exists('developer_role', 'category'):
        op.execute("UPDATE developer_role SET category = 'developer' WHERE category IS NULL")
        op.alter_column('developer_role', 'category', nullable=False, server_default='developer')
    
    # Fix subscription_tier
    if column_exists('subscription_tier', 'status'):
        op.execute("UPDATE subscription_tier SET status = 'active' WHERE status IS NULL")
        op.alter_column('subscription_tier', 'status', nullable=False, server_default='active')
    
    if column_exists('subscription_tier', 'fallback_price_monthly'):
        op.execute("UPDATE subscription_tier SET fallback_price_monthly = '0' WHERE fallback_price_monthly IS NULL")
    
    if column_exists('subscription_tier', 'fallback_price_yearly'):
        op.execute("UPDATE subscription_tier SET fallback_price_yearly = '0' WHERE fallback_price_yearly IS NULL")
    
    # Fix product
    if column_exists('product', 'base_unit'):
        op.execute("UPDATE product SET base_unit = 'g' WHERE base_unit IS NULL")
        op.alter_column('product', 'base_unit', nullable=False, server_default='g')
    
    # Fix ingredient_category color (add the missing column with proper quotes)
    if not column_exists('ingredient_category', 'color'):
        op.add_column('ingredient_category', sa.Column('color', sa.String(7), nullable=True, server_default='#6c757d'))
    
    # Set default values for boolean columns that should default to True/False
    boolean_defaults = [
        ('inventory_item', 'is_perishable', False),
        ('inventory_item', 'is_archived', False),
        ('inventory_item', 'intermediate', False),
        ('unit', 'is_custom', False),
        ('unit', 'is_mapped', False),
        ('permission', 'is_active', True),
        ('developer_permission', 'is_active', True),
        ('recipe', 'is_locked', False),
        ('developer_role', 'is_active', True),
        ('subscription_tier', 'is_customer_facing', True),
        ('subscription_tier', 'is_available', True),
        ('subscription_tier', 'cancel_at_period_end', False),
        ('subscription_tier', 'requires_stripe_billing', True),
        ('tag', 'is_active', True),
        ('user_preferences', 'show_batch_alerts', True),
        ('user_preferences', 'show_timer_alerts', True),
        ('user_preferences', 'show_alert_badges', True),
        ('user_preferences', 'show_expiration_alerts', True),
        ('user_preferences', 'show_quick_actions', True),
        ('user_preferences', 'compact_view', False),
        ('user_preferences', 'show_low_stock_alerts', True),
        ('user_preferences', 'show_fault_alerts', True),
        ('product', 'is_discontinued', False),
        ('ingredient_category', 'is_active', True),
        ('role', 'is_active', True),
        ('user', 'is_deleted', False),
    ]
    
    for table_name, column_name, default_value in boolean_defaults:
        if column_exists(table_name, column_name):
            op.execute(f"UPDATE {table_name} SET {column_name} = {default_value} WHERE {column_name} IS NULL")
    
    # Set integer defaults
    integer_defaults = [
        ('user_preferences', 'max_dashboard_alerts', 10),
        ('recipe_ingredient', 'order_position', 0),
    ]
    
    for table_name, column_name, default_value in integer_defaults:
        if column_exists(table_name, column_name):
            op.execute(f"UPDATE {table_name} SET {column_name} = {default_value} WHERE {column_name} IS NULL")
    
    print("✅ Fixed nullable columns and set proper defaults")


def downgrade():
    """Revert constraint changes"""
    print("=== Reverting constraint fixes ===")
    
    # This would make columns nullable again, but we'll keep it simple
    # In production, you typically don't downgrade constraint fixes
    
    print("✅ Downgrade completed (constraints kept for safety)")
