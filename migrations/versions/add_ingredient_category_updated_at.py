
"""add updated_at to ingredient_category table

Revision ID: add_ingredient_category_updated_at
Revises: 05fab1341ac5
Create Date: 2025-08-01 20:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, inspect


# revision identifiers, used by Alembic.
revision = 'add_ingredient_category_updated_at'
down_revision = '05fab1341ac5'
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
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    print("=== Adding missing updated_at column to ingredient_category ===")
    
    bind = op.get_bind()
    
    # Add updated_at to ingredient_category if missing
    if table_exists('ingredient_category'):
        if not column_exists('ingredient_category', 'updated_at'):
            print("Adding updated_at column to ingredient_category table")
            with op.batch_alter_table('ingredient_category', schema=None) as batch_op:
                batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
            
            # Set initial values to created_at if available, or current timestamp
            if column_exists('ingredient_category', 'created_at'):
                bind.execute(text('UPDATE ingredient_category SET updated_at = created_at WHERE updated_at IS NULL'))
            else:
                bind.execute(text('UPDATE ingredient_category SET updated_at = datetime("now") WHERE updated_at IS NULL'))
            
            print("✅ Added updated_at column to ingredient_category")
        else:
            print("✅ ingredient_category.updated_at already exists")
    else:
        print("⚠️  ingredient_category table doesn't exist")
    
    print("✅ Migration completed")


def downgrade():
    print("=== Removing updated_at column from ingredient_category ===")
    
    if table_exists('ingredient_category') and column_exists('ingredient_category', 'updated_at'):
        print("Removing updated_at from ingredient_category")
        with op.batch_alter_table('ingredient_category', schema=None) as batch_op:
            batch_op.drop_column('updated_at')
    
    print("✅ Downgrade completed")
