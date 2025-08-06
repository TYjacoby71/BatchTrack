"""drop deprecated billing columns

Revision ID: drop_deprecated_billing_columns  
Revises: remove_nonexistent_billing_columns
Create Date: 2025-08-06 05:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'drop_deprecated_billing_columns'
down_revision = '9d2a5c7f8b1e'
branch_labels = None
depends_on = None

def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def upgrade():
    """Drop deprecated billing columns that are no longer needed"""
    print("=== Dropping deprecated billing columns ===")

    # These columns are deprecated and should be removed
    deprecated_columns = [
        'billing_cycle',
        'pricing_category', 
        'price_amount',
        'currency'
    ]

    for col_name in deprecated_columns:
        if column_exists('subscription_tier', col_name):
            print(f"   Dropping {col_name} from subscription_tier")
            try:
                op.drop_column('subscription_tier', col_name)
                print(f"   ✅ Dropped {col_name}")
            except Exception as e:
                print(f"   ⚠️  Could not drop {col_name}: {e}")
        else:
            print(f"   ✅ Column {col_name} doesn't exist (already clean)")

    print("=== Migration completed ===")

def downgrade():
    """Re-add deprecated columns if needed (not recommended)"""
    print("=== Adding back deprecated columns (not recommended) ===")

    try:
        if not column_exists('subscription_tier', 'billing_cycle'):
            op.add_column('subscription_tier', sa.Column('billing_cycle', sa.String(32), nullable=True))

        if not column_exists('subscription_tier', 'pricing_category'):
            op.add_column('subscription_tier', sa.Column('pricing_category', sa.String(32), nullable=True))

        if not column_exists('subscription_tier', 'price_amount'):
            op.add_column('subscription_tier', sa.Column('price_amount', sa.Numeric(10, 2), nullable=True))

        if not column_exists('subscription_tier', 'currency'):
            op.add_column('subscription_tier', sa.Column('currency', sa.String(3), nullable=True))

        print("   ✅ Deprecated columns re-added")
    except Exception as e:
        print(f"   ⚠️  Could not re-add columns: {e}")