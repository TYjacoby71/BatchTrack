
"""add billing columns to organization

Revision ID: add_billing_columns_org
Revises: 9d2a5c7f8b1e
Create Date: 2025-08-05 00:53:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = 'add_billing_columns_org'
down_revision = '9d2a5c7f8b1e'
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists in the database"""
    inspector = inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    if not table_exists(table_name):
        return False
    inspector = inspect(op.get_bind())
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key constraint exists"""
    if not table_exists(table_name):
        return False
    try:
        inspector = inspect(op.get_bind())
        foreign_keys = inspector.get_foreign_keys(table_name)
        return any(fk.get('name') == fk_name for fk in foreign_keys)
    except Exception:
        return False


def upgrade():
    """Add missing billing columns to organization table"""
    print("=== Adding billing columns to organization table ===")
    
    bind = op.get_bind()
    
    # Ensure organization table exists
    if not table_exists('organization'):
        print("   ❌ Organization table does not exist")
        return
    
    print("   ✅ Organization table exists")
    
    # List of billing columns to add
    billing_columns = [
        ('subscription_tier_id', sa.Integer(), True, None),
        ('stripe_subscription_id', sa.String(128), True, None),
        ('stripe_customer_id', sa.String(128), True, None), 
        ('billing_info', sa.Text(), True, None),
        ('next_billing_date', sa.Date(), True, None),
        ('subscription_status', sa.String(32), True, 'inactive'),
        ('signup_source', sa.String(64), True, None),
        ('promo_code', sa.String(32), True, None),
        ('referral_code', sa.String(32), True, None),
        ('contact_email', sa.String(256), True, None),
    ]
    
    # Add missing columns
    for col_name, col_type, nullable, default in billing_columns:
        if not column_exists('organization', col_name):
            print(f"   Adding column: {col_name}")
            try:
                if default is not None:
                    op.add_column('organization', sa.Column(col_name, col_type, nullable=nullable, default=default))
                else:
                    op.add_column('organization', sa.Column(col_name, col_type, nullable=nullable))
                print(f"   ✅ Added {col_name}")
            except Exception as e:
                print(f"   ⚠️  Failed to add {col_name}: {e}")
        else:
            print(f"   ✅ Column {col_name} already exists")
    
    # Add foreign key constraint for subscription_tier_id (only if both tables exist)
    if (column_exists('organization', 'subscription_tier_id') and 
        table_exists('subscription_tier') and 
        not foreign_key_exists('organization', 'fk_organization_subscription_tier_id')):
        
        print("   Adding foreign key constraint for subscription_tier_id...")
        try:
            op.create_foreign_key(
                'fk_organization_subscription_tier_id',
                'organization',
                'subscription_tier',
                ['subscription_tier_id'],
                ['id'],
                ondelete='SET NULL'  # Allow nulls when tier is deleted
            )
            print("   ✅ Added foreign key constraint")
        except Exception as e:
            print(f"   ⚠️  Could not add foreign key constraint: {e}")
    
    # Set default subscription_status for existing organizations that have NULL
    print("   Updating default subscription_status for existing records...")
    try:
        bind.execute(text("""
            UPDATE organization 
            SET subscription_status = 'inactive' 
            WHERE subscription_status IS NULL
        """))
        print("   ✅ Updated subscription_status defaults")
    except Exception as e:
        print(f"   ⚠️  Could not update defaults: {e}")
    
    print("✅ Billing columns migration completed")


def downgrade():
    """Remove billing columns from organization table"""
    print("=== Removing billing columns from organization table ===")
    
    # Remove foreign key constraint first
    try:
        op.drop_constraint('fk_organization_subscription_tier_id', 'organization', type_='foreignkey')
        print("   ✅ Removed foreign key constraint")
    except Exception as e:
        print(f"   ⚠️  Could not remove foreign key: {e}")
    
    # Remove columns
    billing_columns = [
        'subscription_tier_id',
        'stripe_subscription_id', 
        'stripe_customer_id',
        'billing_info',
        'next_billing_date',
        'signup_source',
        'promo_code', 
        'referral_code',
        'contact_email'
    ]
    
    for col_name in billing_columns:
        if column_exists('organization', col_name):
            try:
                op.drop_column('organization', col_name)
                print(f"   ✅ Removed {col_name}")
            except Exception as e:
                print(f"   ⚠️  Could not remove {col_name}: {e}")
    
    print("✅ Billing columns removal completed")
