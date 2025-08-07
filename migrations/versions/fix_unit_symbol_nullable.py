
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
    from sqlalchemy import inspect

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

    print("=== Making unit symbol nullable ===")

    with op.batch_alter_table('unit', schema=None) as batch_op:
        # Make symbol nullable
        batch_op.alter_column('symbol', nullable=True)
        
        # Drop the problematic unique index if it exists
        try:
            batch_op.drop_index('ix_unit_standard_unique')
        except Exception:
            pass  # Index might not exist
        
        # Drop the problematic unique constraint if it exists
        try:
            batch_op.drop_constraint('_unit_name_org_uc')
        except Exception:
            pass  # Constraint might not exist
        
        # Add proper unique constraint for custom units
        batch_op.create_unique_constraint('_unit_name_org_uc', ['name', 'organization_id'])

    print("✅ Unit symbol nullable migration completed")


def downgrade():
    """Restore unit symbol as required"""
    print("=== Restoring unit symbol as required ===")

    with op.batch_alter_table('unit', schema=None) as batch_op:
        # Make symbol required again (fill nulls first)
        connection = op.get_bind()
        connection.execute(sa.text("UPDATE unit SET symbol = name WHERE symbol IS NULL"))
        
        batch_op.alter_column('symbol', nullable=False)
        
        # Drop the new constraint
        try:
            batch_op.drop_constraint('_unit_name_org_uc')
        except Exception:
            pass
        
        # Restore old constraints
        batch_op.create_index('ix_unit_standard_unique', ['name'], unique=True)

    print("✅ Unit symbol downgrade completed")
