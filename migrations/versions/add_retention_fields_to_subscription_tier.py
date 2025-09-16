
"""add retention fields to subscription_tier

Revision ID: 20250916203500
Revises: 20250913014500
Create Date: 2025-09-16 20:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision = '20250916203500'
down_revision = '20250913014500'
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


def constraint_exists(table_name, constraint_name):
    """Check if a constraint exists"""
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    try:
        # Check unique constraints
        unique_constraints = inspector.get_unique_constraints(table_name)
        if any(c.get('name') == constraint_name for c in unique_constraints):
            return True
        
        # Check indexes that might serve as unique constraints
        indexes = inspector.get_indexes(table_name)
        return any(idx.get('name') == constraint_name for idx in indexes)
    except Exception:
        return False


def upgrade():
    """Add missing retention fields to subscription_tier table"""
    
    print("=== Adding retention fields to subscription_tier ===")
    
    # Verify subscription_tier table exists
    if not table_exists('subscription_tier'):
        print("   ❌ subscription_tier table does not exist - skipping migration")
        return
    
    # Add data retention policy columns
    retention_columns = [
        ('data_retention_days', 'Number of days to retain long-term data'),
        ('retention_notice_days', 'Days before deletion to start user notification'),
        ('storage_addon_retention_days', 'Days a storage add-on purchase extends retention')
    ]
    
    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        for col_name, description in retention_columns:
            if not column_exists('subscription_tier', col_name):
                print(f"   Adding missing {col_name} column...")
                batch_op.add_column(sa.Column(col_name, sa.Integer, nullable=True))
                print(f"   ✅ {col_name} column added successfully")
            else:
                print(f"   ⚠️  {col_name} column already exists")
    
    # Add stripe_storage_lookup_key if missing
    if not column_exists('subscription_tier', 'stripe_storage_lookup_key'):
        print("   Adding stripe_storage_lookup_key column...")
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            batch_op.add_column(sa.Column('stripe_storage_lookup_key', sa.String(128), nullable=True))
        print("   ✅ stripe_storage_lookup_key column added successfully")
        
        # Add unique constraint for stripe_storage_lookup_key if it doesn't exist
        constraint_name = 'uq_subscription_tier_stripe_storage_lookup_key'
        if not constraint_exists('subscription_tier', constraint_name):
            try:
                with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
                    batch_op.create_unique_constraint(
                        constraint_name, 
                        ['stripe_storage_lookup_key']
                    )
                print(f"   ✅ Created unique constraint {constraint_name}")
            except Exception as e:
                print(f"   ⚠️  Could not create unique constraint: {e}")
        else:
            print(f"   ⚠️  Unique constraint {constraint_name} already exists")
    else:
        print("   ⚠️  stripe_storage_lookup_key column already exists")
    
    print("✅ Retention fields migration completed")


def downgrade():
    """Remove retention fields"""
    print("=== Removing retention fields from subscription_tier ===")
    
    if not table_exists('subscription_tier'):
        print("   ⚠️  subscription_tier table does not exist - nothing to remove")
        return
    
    retention_columns = [
        'data_retention_days', 'retention_notice_days', 
        'storage_addon_retention_days', 'stripe_storage_lookup_key'
    ]
    
    # Remove unique constraint first if it exists
    constraint_name = 'uq_subscription_tier_stripe_storage_lookup_key'
    if constraint_exists('subscription_tier', constraint_name):
        try:
            with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
                batch_op.drop_constraint(constraint_name, type_='unique')
            print(f"   ✅ Dropped unique constraint {constraint_name}")
        except Exception as e:
            print(f"   ⚠️  Could not drop constraint {constraint_name}: {e}")
    
    # Remove columns
    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        for col_name in retention_columns:
            if column_exists('subscription_tier', col_name):
                try:
                    batch_op.drop_column(col_name)
                    print(f"   ✅ Dropped column {col_name}")
                except Exception as e:
                    print(f"   ⚠️  Could not drop column {col_name}: {e}")
            else:
                print(f"   ⚠️  Column {col_name} does not exist")
    
    print("✅ Retention fields removal completed")
