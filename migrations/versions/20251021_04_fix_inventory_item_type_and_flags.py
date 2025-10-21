"""
Ensure inventory_item.type exists and add core flags used by init-production

Revision ID: 20251021_04
Revises: 20251021_03
Create Date: 2025-10-21 20:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision = "20251021_04"
down_revision = "20251021_03"
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    try:
        bind = op.get_bind()
        inspector = inspect(bind)
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def column_exists(table: str, column: str) -> bool:
    if not table_exists(table):
        return False
    try:
        bind = op.get_bind()
        inspector = inspect(bind)
        cols = [c["name"] for c in inspector.get_columns(table)]
        return column in cols
    except Exception:
        return False


def index_exists(table: str, index_name: str) -> bool:
    try:
        bind = op.get_bind()
        inspector = inspect(bind)
        indexes = [idx["name"] for idx in inspector.get_indexes(table)]
        return index_name in indexes
    except Exception:
        return False


def safe_add_column(table: str, column: sa.Column) -> bool:
    if not table_exists(table):
        print(f"   ⚠️  Table {table} does not exist - skipping {column.name}")
        return False
    if column_exists(table, column.name):
        print(f"   ✅ {table}.{column.name} already exists")
        return False
    try:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(column)
        print(f"   ✅ Added {table}.{column.name}")
        return True
    except Exception as e:
        print(f"   ⚠️  Could not add column {table}.{column.name}: {e}")
        return False


def safe_create_index(table: str, index_name: str, columns: list[str], unique: bool = False) -> bool:
    if not table_exists(table):
        print(f"   ⚠️  Table {table} does not exist - skipping index {index_name}")
        return False
    if index_exists(table, index_name):
        print(f"   ✅ Index {index_name} already exists on {table}")
        return False
    try:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.create_index(index_name, columns, unique=unique)
        print(f"   ✅ Created index {index_name} on {table}({', '.join(columns)})")
        return True
    except Exception as e:
        print(f"   ⚠️  Could not create index {index_name} on {table}: {e}")
        return False


def upgrade() -> None:
    print("=== Fix inventory_item.type and core fields for init-production ===")

    if not table_exists("inventory_item"):
        print("   ⚠️  inventory_item table is missing; nothing to fix")
        return

    bind = op.get_bind()

    # 1) Ensure inventory_item.type exists (rename from legacy item_type if present)
    try:
        has_type = column_exists("inventory_item", "type")
        has_item_type = column_exists("inventory_item", "item_type")

        if not has_type and has_item_type:
            print("   ↻ Renaming inventory_item.item_type -> type ...")
            try:
                # Prefer batch rename for cross-dialect support
                with op.batch_alter_table("inventory_item", schema=None) as batch_op:
                    batch_op.alter_column("item_type", new_column_name="type")
                print("   ✅ Renamed item_type to type")
            except Exception as e:
                print(f"   ⚠️  Batch rename failed ({e}), attempting direct SQL rename ...")
                try:
                    bind.execute(text("ALTER TABLE inventory_item RENAME COLUMN item_type TO type"))
                    print("   ✅ Renamed item_type to type via SQL")
                except Exception as e2:
                    print(f"   ❌ Could not rename column: {e2}")
                    # Fallback: add type, copy values, drop item_type
                    added = safe_add_column("inventory_item", sa.Column("type", sa.String(length=32), nullable=True))
                    if added:
                        try:
                            bind.execute(text("UPDATE inventory_item SET type = item_type WHERE type IS NULL"))
                            print("   ✅ Backfilled type from item_type")
                        except Exception as copy_err:
                            print(f"   ⚠️  Could not backfill type from item_type: {copy_err}")
                        # try to drop old column safely
                        try:
                            with op.batch_alter_table("inventory_item", schema=None) as batch_op:
                                batch_op.drop_column("item_type")
                            print("   ✅ Dropped legacy item_type column")
                        except Exception as drop_err:
                            print(f"   ⚠️  Could not drop legacy item_type: {drop_err}")
        elif not has_type and not has_item_type:
            # Neither exists: create type as nullable then backfill default
            safe_add_column("inventory_item", sa.Column("type", sa.String(length=32), nullable=True))
            print("   ℹ️  Added type as new column (no legacy column found)")
        else:
            print("   ✅ inventory_item.type already present")

        # Backfill NULLs to model default 'ingredient'
        if column_exists("inventory_item", "type"):
            try:
                bind.execute(text("UPDATE inventory_item SET type = 'ingredient' WHERE type IS NULL"))
                print("   ✅ Backfilled NULL type values to 'ingredient'")
            except Exception as e:
                print(f"   ⚠️  Could not backfill NULL type values: {e}")
    except Exception as e:
        print(f"   ⚠️  Error ensuring inventory_item.type: {e}")

    # 2) Ensure core flags and fields exist that init-production and models rely on
    safe_add_column("inventory_item", sa.Column("is_active", sa.Boolean(), nullable=True))
    safe_add_column("inventory_item", sa.Column("is_archived", sa.Boolean(), nullable=True))
    safe_add_column("inventory_item", sa.Column("intermediate", sa.Boolean(), nullable=True))
    safe_add_column("inventory_item", sa.Column("is_perishable", sa.Boolean(), nullable=True))
    safe_add_column("inventory_item", sa.Column("shelf_life_days", sa.Integer(), nullable=True))
    safe_add_column("inventory_item", sa.Column("created_by", sa.Integer(), nullable=True))
    safe_add_column("inventory_item", sa.Column("density_source", sa.String(length=32), nullable=True))

    # 3) Create index on type if missing
    try:
        safe_create_index("inventory_item", "ix_inventory_item_type", ["type"], unique=False)
    except Exception as e:
        print(f"   ⚠️  Could not create ix_inventory_item_type: {e}")

    print("✅ inventory_item.type and core fields ensured")


def downgrade() -> None:
    # Conservative downgrade: do not drop columns or index in production
    print("=== Downgrade no-op: preserving added/renamed columns and indexes ===")
