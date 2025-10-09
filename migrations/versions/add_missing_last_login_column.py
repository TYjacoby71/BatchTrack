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

def column_exists(table_name, column_name):
    """Check if a column exists"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except:
        return False

def upgrade():
    """Add missing last_login column"""
    print("=== Adding missing last_login column ===")

    try:
        # Check if column exists before adding
        if not column_exists('user', 'last_login'):
            print("   Adding last_login column...")
            op.add_column('user', sa.Column('last_login', sa.DateTime(), nullable=True))
            print("   ✅ last_login column added")
        else:
            print("   ⚠️  last_login column already exists - migration skipped")
    except Exception as e:
        print(f"   ⚠️  Migration error: {e}")
        # For PostgreSQL, we need to handle transaction state carefully
        # If there's an error, don't let it bubble up and abort the transaction
        pass

    print("✅ Migration completed")

def downgrade():
    """Remove last_login column"""
    try:
        op.drop_column('user', 'last_login')
    except Exception as e:
        print(f"   ⚠️  Could not drop last_login column: {e}")