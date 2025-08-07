
"""fix fallback_price column type from Numeric to String

Revision ID: fix_fallback_price_type
Revises: 9a2b8c4d5e6f
Create Date: 2025-08-07 00:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'fix_fallback_price_type'
down_revision = '9a2b8c4d5e6f'
branch_labels = None
depends_on = None

def upgrade():
    """Fix fallback_price column type from Numeric to String to match model"""
    
    # Get database connection and inspector
    connection = op.get_bind()
    inspector = inspect(connection)
    
    def column_exists(table_name, column_name):
        """Check if a column exists in a table"""
        try:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return column_name in columns
        except Exception:
            return False
    
    print("=== Fixing fallback_price column type ===")
    
    if column_exists('subscription_tier', 'fallback_price'):
        print("   Converting fallback_price from Numeric to String...")
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            # Change the column type from Numeric to String
            batch_op.alter_column('fallback_price',
                   existing_type=sa.Numeric(precision=10, scale=2),
                   type_=sa.String(32),
                   existing_nullable=True)
        print("✅ fallback_price column type fixed")
    else:
        print("   ⚠️  fallback_price column doesn't exist, skipping")

def downgrade():
    """Revert fallback_price column type back to Numeric"""
    
    print("=== Reverting fallback_price column type ===")
    
    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        batch_op.alter_column('fallback_price',
               existing_type=sa.String(32),
               type_=sa.Numeric(precision=10, scale=2),
               existing_nullable=True)
    
    print("✅ fallback_price column type reverted to Numeric")
