
"""add missing last_login column

Revision ID: add_missing_last_login_column
Revises: add_batch_id_to_inventory_lot
Create Date: 2025-08-25 16:55:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_missing_last_login_column'
down_revision = 'add_batch_id_to_inventory_lot'
branch_labels = None
depends_on = None

def upgrade():
    """Add missing last_login column to user table"""
    print("=== Adding missing last_login column ===")
    
    # Simple approach - just add the column if it doesn't exist
    try:
        op.add_column('user', sa.Column('last_login', sa.DateTime(), nullable=True))
        print("   ✅ last_login column added successfully")
    except Exception as e:
        if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower():
            print("   ⚠️  last_login column already exists - migration skipped")
        else:
            print(f"   ❌ Error adding last_login column: {e}")
            raise
    
    print("✅ Migration completed")

def downgrade():
    """Remove last_login column"""
    try:
        op.drop_column('user', 'last_login')
    except Exception as e:
        print(f"   ⚠️  Could not drop last_login column: {e}")
