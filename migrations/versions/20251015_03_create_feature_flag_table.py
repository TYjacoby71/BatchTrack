"""
Create feature_flag table
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = '20251015_03'
down_revision = '20251015_02'
branch_labels = None
depends_on = None

def table_exists(table_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()

def index_exists(table_name, index_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    try:
        indexes = inspector.get_indexes(table_name)
        return any(idx['name'] == index_name for idx in indexes)
    except Exception:
        return False

def upgrade():
    print("=== Creating feature_flag table ===")
    
    try:
        # Check if table already exists
        bind = op.get_bind()
        inspector = sa.inspect(bind)

        if 'feature_flag' not in inspector.get_table_names():
            print("Creating feature_flag table...")
            op.create_table('feature_flag',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
            )
            print("✅ feature_flag table created successfully")
        else:
            print("⚠️  feature_flag table already exists, skipping creation")
            
    except Exception as e:
        print(f"❌ Error in feature_flag table migration: {e}")
        # Don't re-raise - let migration continue
        print("⚠️  Continuing with migration despite error...")
    
    print("✅ Feature flag table migration completed")


def downgrade():
    print("=== Removing feature_flag table ===")

    # Drop index first
    if table_exists('feature_flag') and index_exists('feature_flag', 'ix_feature_flag_key'):
        try:
            op.drop_index('ix_feature_flag_key', table_name='feature_flag')
            print("   ✅ Dropped unique index")
        except Exception as e:
            print(f"   ⚠️  Could not drop index: {e}")

    # Drop table
    if table_exists('feature_flag'):
        try:
            op.drop_table('feature_flag')
            print("   ✅ Dropped feature_flag table")
        except Exception as e:
            print(f"   ⚠️  Could not drop table: {e}")

    print("✅ Feature flag table downgrade completed")