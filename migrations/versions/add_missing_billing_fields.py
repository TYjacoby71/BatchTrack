
"""Add missing billing fields to organization table

Revision ID: a1b2c3d4e5f6
Revises: add_offline_billing_support
Create Date: 2025-08-06 06:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'drop_deprecated_billing_columns'
branch_labels = None
depends_on = None

def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    bind = op.get_bind()
    inspector = inspect(bind)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

def table_exists(table_name):
    """Check if a table exists"""
    bind = op.get_bind()
    inspector = inspect(bind)
    try:
        return table_name in inspector.get_table_names()
    except Exception:
        return False

def upgrade():
    """Add missing billing fields to organization table"""
    print("=== Adding missing billing fields to organization table ===")
    
    if not table_exists('organization'):
        print("   ❌ Organization table does not exist")
        return
    
    # Define columns to add if they don't exist
    columns_to_add = [
        ('billing_status', sa.String(50), 'active'),
        ('stripe_customer_id', sa.String(255), None),
        ('stripe_subscription_id', sa.String(128), None),
        ('whop_license_key', sa.String(128), None),
        ('whop_product_tier', sa.String(32), None),
        ('whop_verified', sa.Boolean(), False),
    ]
    
    for col_name, col_type, default_value in columns_to_add:
        if not column_exists('organization', col_name):
            print(f"   Adding column: {col_name}")
            try:
                if default_value is not None:
                    if isinstance(default_value, bool):
                        op.add_column('organization', sa.Column(col_name, col_type, nullable=True, default=default_value))
                    else:
                        op.add_column('organization', sa.Column(col_name, col_type, nullable=True, default=default_value))
                else:
                    op.add_column('organization', sa.Column(col_name, col_type, nullable=True))
                print(f"   ✅ Added {col_name}")
            except Exception as e:
                print(f"   ⚠️  Failed to add {col_name}: {e}")
        else:
            print(f"   ✅ Column {col_name} already exists")
    
    # Update existing records with default values where NULL
    print("   Updating default values for existing records...")
    try:
        # Use raw SQL to handle both SQLite and PostgreSQL
        bind = op.get_bind()
        
        # Set billing_status default
        if column_exists('organization', 'billing_status'):
            bind.execute(sa.text("""
                UPDATE organization 
                SET billing_status = 'active' 
                WHERE billing_status IS NULL
            """))
        
        # Set whop_verified default
        if column_exists('organization', 'whop_verified'):
            bind.execute(sa.text("""
                UPDATE organization 
                SET whop_verified = 0 
                WHERE whop_verified IS NULL
            """))
            
        print("   ✅ Updated default values")
    except Exception as e:
        print(f"   ⚠️  Could not update defaults: {e}")
    
    print("✅ Missing billing fields migration completed")

def downgrade():
    """Remove the billing fields"""
    print("=== Removing billing fields from organization table ===")
    
    columns_to_remove = [
        'billing_status',
        'stripe_customer_id', 
        'stripe_subscription_id',
        'whop_license_key',
        'whop_product_tier',
        'whop_verified'
    ]
    
    for col_name in columns_to_remove:
        if column_exists('organization', col_name):
            try:
                op.drop_column('organization', col_name)
                print(f"   ✅ Removed {col_name}")
            except Exception as e:
                print(f"   ⚠️  Could not remove {col_name}: {e}")
    
    print("✅ Billing fields removal completed")
