
"""Add inventory cost method toggle and valuation method fields

Revision ID: 20250922_02
Revises: 20250922_01_align_extras
Create Date: 2025-09-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = '20250922_02'
down_revision = '20250922_01_align_extras'
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
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def constraint_exists(table_name, constraint_name):
    """Check if a constraint exists on a table"""
    if not table_exists(table_name):
        return False
    try:
        bind = op.get_bind()
        result = bind.execute(text("""
            SELECT COUNT(*)
            FROM information_schema.table_constraints
            WHERE table_name = :table_name
            AND constraint_name = :constraint_name
        """), {"table_name": table_name, "constraint_name": constraint_name})
        return result.scalar() > 0
    except Exception:
        return False


def upgrade():
    print("=== Adding inventory cost method toggle and valuation method fields ===")
    
    # Organization: add inventory cost method fields
    if table_exists('organization'):
        if not column_exists('organization', 'inventory_cost_method'):
            print("Adding inventory_cost_method to organization...")
            try:
                op.add_column('organization', sa.Column('inventory_cost_method', sa.String(length=16), nullable=True))
                print("✅ Added inventory_cost_method column")
            except Exception as e:
                print(f"⚠️  Error adding inventory_cost_method: {e}")
        else:
            print("inventory_cost_method column already exists")

        if not column_exists('organization', 'inventory_cost_method_changed_at'):
            print("Adding inventory_cost_method_changed_at to organization...")
            try:
                op.add_column('organization', sa.Column('inventory_cost_method_changed_at', sa.DateTime(), nullable=True))
                print("✅ Added inventory_cost_method_changed_at column")
            except Exception as e:
                print(f"⚠️  Error adding inventory_cost_method_changed_at: {e}")
        else:
            print("inventory_cost_method_changed_at column already exists")

    # UnifiedInventoryHistory: add valuation method for audit
    if table_exists('unified_inventory_history'):
        if not column_exists('unified_inventory_history', 'valuation_method'):
            print("Adding valuation_method to unified_inventory_history...")
            try:
                op.add_column('unified_inventory_history', sa.Column('valuation_method', sa.String(length=16), nullable=True))
                print("✅ Added valuation_method column")
            except Exception as e:
                print(f"⚠️  Error adding valuation_method: {e}")
        else:
            print("valuation_method column already exists")

    # Batch: snapshot cost method and timestamp
    if table_exists('batch'):
        if not column_exists('batch', 'cost_method'):
            print("Adding cost_method to batch...")
            try:
                op.add_column('batch', sa.Column('cost_method', sa.String(length=16), nullable=True))
                print("✅ Added cost_method column")
            except Exception as e:
                print(f"⚠️  Error adding cost_method: {e}")
        else:
            print("cost_method column already exists")

        if not column_exists('batch', 'cost_method_locked_at'):
            print("Adding cost_method_locked_at to batch...")
            try:
                op.add_column('batch', sa.Column('cost_method_locked_at', sa.DateTime(), nullable=True))
                print("✅ Added cost_method_locked_at column")
            except Exception as e:
                print(f"⚠️  Error adding cost_method_locked_at: {e}")
        else:
            print("cost_method_locked_at column already exists")

    print("✅ Inventory cost method migration completed")


def downgrade():
    print("=== Reverting inventory cost method toggle and valuation method fields ===")
    
    # Reverse in safe order
    if table_exists('batch'):
        if column_exists('batch', 'cost_method_locked_at'):
            try:
                op.drop_column('batch', 'cost_method_locked_at')
                print("Dropped cost_method_locked_at from batch")
            except Exception as e:
                print(f"⚠️  Error dropping cost_method_locked_at: {e}")

        if column_exists('batch', 'cost_method'):
            try:
                op.drop_column('batch', 'cost_method')
                print("Dropped cost_method from batch")
            except Exception as e:
                print(f"⚠️  Error dropping cost_method: {e}")

    if table_exists('unified_inventory_history'):
        if column_exists('unified_inventory_history', 'valuation_method'):
            try:
                op.drop_column('unified_inventory_history', 'valuation_method')
                print("Dropped valuation_method from unified_inventory_history")
            except Exception as e:
                print(f"⚠️  Error dropping valuation_method: {e}")

    if table_exists('organization'):
        if column_exists('organization', 'inventory_cost_method_changed_at'):
            try:
                op.drop_column('organization', 'inventory_cost_method_changed_at')
                print("Dropped inventory_cost_method_changed_at from organization")
            except Exception as e:
                print(f"⚠️  Error dropping inventory_cost_method_changed_at: {e}")

        if column_exists('organization', 'inventory_cost_method'):
            try:
                op.drop_column('organization', 'inventory_cost_method')
                print("Dropped inventory_cost_method from organization")
            except Exception as e:
                print(f"⚠️  Error dropping inventory_cost_method: {e}")

    print("✅ Downgrade completed successfully")
