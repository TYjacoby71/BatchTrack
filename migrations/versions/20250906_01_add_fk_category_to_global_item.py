
"""Add foreign key from global_item to ingredient_category

Revision ID: 20250906_01
Revises: 20250905_01
Create Date: 2025-09-06 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250906_01'
down_revision = '20250905_01'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key exists"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = inspector.get_foreign_keys(table_name)
        return any(fk.get('name') == fk_name for fk in fks)
    except Exception:
        return False


def index_exists(table_name, index_name):
    """Check if an index exists"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = inspector.get_indexes(table_name)
        return any(idx.get('name') == index_name for idx in indexes)
    except Exception:
        return False


def upgrade():
    """Add ingredient_category_id column and foreign key to global_item"""
    print("=== Adding ingredient_category_id to global_item ===")

    # Check if column already exists
    if not column_exists('global_item', 'ingredient_category_id'):
        print("   Adding ingredient_category_id column...")
        with op.batch_alter_table('global_item') as batch_op:
            batch_op.add_column(sa.Column('ingredient_category_id', sa.Integer(), nullable=True))
        print("   ✅ Added ingredient_category_id column")
    else:
        print("   ✅ ingredient_category_id column already exists - skipping")

    # Check if index exists
    index_name = 'ix_global_item_ingredient_category_id'
    if not index_exists('global_item', index_name):
        print("   Adding index...")
        with op.batch_alter_table('global_item') as batch_op:
            batch_op.create_index(batch_op.f('ix_global_item_ingredient_category_id'), ['ingredient_category_id'], unique=False)
        print("   ✅ Added index")
    else:
        print("   ✅ Index already exists - skipping")

    # Check if foreign key exists
    fk_name = 'fk_global_item_ingredient_category_id'
    if not foreign_key_exists('global_item', fk_name):
        print("   Adding foreign key constraint...")
        with op.batch_alter_table('global_item') as batch_op:
            batch_op.create_foreign_key('fk_global_item_ingredient_category_id', 'ingredient_category', ['ingredient_category_id'], ['id'])
        print("   ✅ Added foreign key constraint")
    else:
        print("   ✅ Foreign key constraint already exists - skipping")

    print("✅ Migration completed successfully")


def downgrade():
    """Remove ingredient_category_id column and foreign key from global_item"""
    print("=== Removing ingredient_category_id from global_item ===")

    # Check if column exists before trying to drop it
    if column_exists('global_item', 'ingredient_category_id'):
        print("   Removing foreign key constraint and column...")
        with op.batch_alter_table('global_item') as batch_op:
            # Drop foreign key constraint
            try:
                batch_op.drop_constraint('fk_global_item_ingredient_category_id', type_='foreignkey')
                print("   ✅ Dropped foreign key constraint")
            except Exception as e:
                print(f"   ⚠️  Could not drop foreign key constraint: {e}")

            # Drop index
            try:
                batch_op.drop_index(batch_op.f('ix_global_item_ingredient_category_id'))
                print("   ✅ Dropped index")
            except Exception as e:
                print(f"   ⚠️  Could not drop index: {e}")

            # Drop column
            batch_op.drop_column('ingredient_category_id')
            print("   ✅ Dropped ingredient_category_id column")
    else:
        print("   ✅ ingredient_category_id column does not exist - skipping")

    print("✅ Downgrade completed successfully")
