
"""Add portion_unit_id FK to recipe and batch

Revision ID: 20250925_03
Revises: 20250925_02
Create Date: 2025-09-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


def safe_add_column(table_name, column):
    """Add column if it doesn't already exist"""
    connection = op.get_bind()
    inspector = inspect(connection)
    existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
    
    if column.name not in existing_columns:
        op.add_column(table_name, column)
        print(f"Added column {column.name} to {table_name}")
    else:
        print(f"Column {column.name} already exists in {table_name}, skipping")


def safe_drop_column(table_name, column_name):
    """Drop column if it exists"""
    connection = op.get_bind()
    inspector = inspect(connection)
    existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
    
    if column_name in existing_columns:
        op.drop_column(table_name, column_name)
        print(f"Dropped column {column_name} from {table_name}")
    else:
        print(f"Column {column_name} does not exist in {table_name}, skipping")


# revision identifiers, used by Alembic.
revision = '20250925_03'
down_revision = '20250925_02'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name
    inspector = inspect(bind)

    is_sqlite = dialect == 'sqlite'

    # SQLite: add simple integer columns (no FK constraints via ALTER)
    if is_sqlite:
        safe_add_column('recipe', sa.Column('portion_unit_id', sa.Integer(), nullable=True))
        safe_add_column('batch', sa.Column('portion_unit_id', sa.Integer(), nullable=True))
        return

    # Non-SQLite (e.g., Postgres): add column then create FK in batch mode
    if 'recipe' in inspector.get_table_names():
        existing = [c['name'] for c in inspector.get_columns('recipe')]
        if 'portion_unit_id' not in existing:
            with op.batch_alter_table('recipe') as batch_op:
                batch_op.add_column(sa.Column('portion_unit_id', sa.Integer(), nullable=True))
                try:
                    batch_op.create_foreign_key('fk_recipe_portion_unit', 'unit', ['portion_unit_id'], ['id'])
                except Exception as e:
                    print(f"Note: Could not create FK on recipe.portion_unit_id: {e}")
        else:
            print("Column portion_unit_id already exists in recipe, skipping")

    if 'batch' in inspector.get_table_names():
        existing = [c['name'] for c in inspector.get_columns('batch')]
        if 'portion_unit_id' not in existing:
            with op.batch_alter_table('batch') as batch_op:
                batch_op.add_column(sa.Column('portion_unit_id', sa.Integer(), nullable=True))
                try:
                    batch_op.create_foreign_key('fk_batch_portion_unit', 'unit', ['portion_unit_id'], ['id'])
                except Exception as e:
                    print(f"Note: Could not create FK on batch.portion_unit_id: {e}")
        else:
            print("Column portion_unit_id already exists in batch, skipping")


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name
    inspector = inspect(bind)

    is_sqlite = dialect == 'sqlite'

    # On non-SQLite, attempt to drop FK constraints before dropping columns
    if not is_sqlite:
        if 'recipe' in inspector.get_table_names():
            try:
                with op.batch_alter_table('recipe') as batch_op:
                    try:
                        batch_op.drop_constraint('fk_recipe_portion_unit', type_='foreignkey')
                    except Exception:
                        pass
            except Exception:
                pass
        if 'batch' in inspector.get_table_names():
            try:
                with op.batch_alter_table('batch') as batch_op:
                    try:
                        batch_op.drop_constraint('fk_batch_portion_unit', type_='foreignkey')
                    except Exception:
                        pass
            except Exception:
                pass

    # Remove columns using safe operations
    safe_drop_column('recipe', 'portion_unit_id')
    safe_drop_column('batch', 'portion_unit_id')
