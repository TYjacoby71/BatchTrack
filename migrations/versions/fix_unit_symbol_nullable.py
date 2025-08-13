"""make unit symbol nullable for custom units

Revision ID: fix_unit_symbol_nullable
Revises: b5c7d8e9f1a2
Create Date: 2025-08-07 21:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_unit_symbol_nullable'
down_revision = 'b5c7d8e9f1a2'
branch_labels = None
depends_on = None


def upgrade():
    """Make unit symbol nullable for custom units"""
    print("=== Making unit symbol nullable ===")

    # Check if the index exists before trying to drop it
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = inspector.get_indexes('unit')
    index_names = [idx['name'] for idx in indexes]

    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('unit', schema=None) as batch_op:
        # Drop the unique index first if it exists
        if 'ix_unit_standard_unique' in index_names:
            try:
                batch_op.drop_index('ix_unit_standard_unique')
                print("   ✅ Dropped ix_unit_standard_unique index")
            except Exception as e:
                print(f"   ⚠️  Could not drop index ix_unit_standard_unique: {e}")
        else:
            print("   ℹ️  Index ix_unit_standard_unique doesn't exist, skipping")

        # Make symbol nullable
        batch_op.alter_column('symbol', 
                             existing_type=sa.String(10),
                             nullable=True)
        print("   ✅ Made symbol column nullable")

        # Recreate index without unique constraint for symbol (only if symbol index doesn't exist)
        if 'ix_unit_symbol' not in index_names:
            batch_op.create_index('ix_unit_symbol', ['symbol'])
            print("   ✅ Created new ix_unit_symbol index")
        else:
            print("   ℹ️  Index ix_unit_symbol already exists")

    print("✅ Migration completed: Unit symbol is now nullable")


def downgrade():
    """Restore unit symbol as required"""
    print("=== Restoring unit symbol as required ===")

    # Check what indexes exist first
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = inspector.get_indexes('unit')
    index_names = [idx['name'] for idx in indexes]

    with op.batch_alter_table('unit', schema=None) as batch_op:
        # Make symbol required again (fill nulls first)
        connection = op.get_bind()
        connection.execute(sa.text("UPDATE unit SET symbol = name WHERE symbol IS NULL"))

        batch_op.alter_column('symbol', nullable=False)

        # Drop the symbol index if it exists
        if 'ix_unit_symbol' in index_names:
            try:
                batch_op.drop_index('ix_unit_symbol')
                print("   ✅ Dropped ix_unit_symbol index")
            except Exception as e:
                print(f"   ⚠️  Could not drop index ix_unit_symbol: {e}")

        # Create a simple name index (not unique to avoid conflicts)
        if 'ix_unit_name' not in index_names:
            batch_op.create_index('ix_unit_name', ['name'])
            print("   ✅ Created ix_unit_name index")

    print("✅ Unit symbol downgrade completed")