
"""Add offline billing support and missing billing fields

Revision ID: 3f7a8b9c2d5e
Revises: drop_deprecated_billing_columns
Create Date: 2025-08-06 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision = '3f7a8b9c2d5e'
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
    """Add offline billing support and missing billing fields"""
    print("=== Adding offline billing support and missing billing fields ===")
    
    bind = op.get_bind()
    
    # Add offline support columns to subscription_tier
    if table_exists('subscription_tier'):
        print("   Adding offline support to subscription_tier...")
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            if not column_exists('subscription_tier', 'last_billing_sync'):
                batch_op.add_column(sa.Column('last_billing_sync', sa.DateTime(), nullable=True))
                print("   ✅ Added last_billing_sync")
            
            if not column_exists('subscription_tier', 'grace_period_days'):
                batch_op.add_column(sa.Column('grace_period_days', sa.Integer(), default=7))
                print("   ✅ Added grace_period_days")

    # Add offline support and missing billing fields to organization
    if table_exists('organization'):
        print("   Adding fields to organization...")
        
        # Define all columns to add
        columns_to_add = [
            # Offline support columns
            ('last_online_sync', sa.DateTime(), None),
            ('offline_tier_cache', sa.JSON(), None),
            # Missing billing fields
            ('billing_status', sa.String(50), 'active'),
            ('stripe_customer_id', sa.String(255), None),
            ('stripe_subscription_id', sa.String(128), None),
            ('whop_license_key', sa.String(128), None),
            ('whop_product_tier', sa.String(32), None),
            ('whop_verified', sa.Boolean(), False),
        ]
        
        with op.batch_alter_table('organization', schema=None) as batch_op:
            for col_name, col_type, default_value in columns_to_add:
                if not column_exists('organization', col_name):
                    print(f"   Adding column: {col_name}")
                    try:
                        if default_value is not None:
                            batch_op.add_column(sa.Column(col_name, col_type, nullable=True, default=default_value))
                        else:
                            batch_op.add_column(sa.Column(col_name, col_type, nullable=True))
                        print(f"   ✅ Added {col_name}")
                    except Exception as e:
                        print(f"   ⚠️  Failed to add {col_name}: {e}")
                else:
                    print(f"   ✅ Column {col_name} already exists")
        
        # Update existing records with default values where NULL
        print("   Updating default values for existing records...")
        try:
            # Set billing_status default
            if column_exists('organization', 'billing_status'):
                bind.execute(text("""
                    UPDATE organization 
                    SET billing_status = 'active' 
                    WHERE billing_status IS NULL
                """))
            
            # Set whop_verified default
            if column_exists('organization', 'whop_verified'):
                bind.execute(text("""
                    UPDATE organization 
                    SET whop_verified = 0 
                    WHERE whop_verified IS NULL
                """))
                
            print("   ✅ Updated default values")
        except Exception as e:
            print(f"   ⚠️  Could not update defaults: {e}")
    
    print("✅ Offline billing and missing fields migration completed")

def downgrade():
    """Remove offline billing support and missing billing fields"""
    print("=== Removing offline billing support and missing billing fields ===")
    
    # Remove columns from organization
    if table_exists('organization'):
        with op.batch_alter_table('organization', schema=None) as batch_op:
            columns_to_remove = [
                'offline_tier_cache',
                'last_online_sync',
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
                        batch_op.drop_column(col_name)
                        print(f"   ✅ Removed {col_name}")
                    except Exception as e:
                        print(f"   ⚠️  Could not remove {col_name}: {e}")
    
    # Remove columns from subscription_tier
    if table_exists('subscription_tier'):
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            if column_exists('subscription_tier', 'grace_period_days'):
                batch_op.drop_column('grace_period_days')
                print("   ✅ Removed grace_period_days")
            
            if column_exists('subscription_tier', 'last_billing_sync'):
                batch_op.drop_column('last_billing_sync')
                print("   ✅ Removed last_billing_sync")
    
    print("✅ Offline billing and missing fields removal completed")
