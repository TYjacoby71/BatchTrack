"""
Add organization_id column to recipe_consumable table

Revision ID: 20250908_01
Revises: 2025090502
Create Date: 2025-09-08
"""

from alembic import op
import sqlalchemy as sa

# Helper functions to check for table and column existence
def table_exists(table_name):
    from sqlalchemy.engine import reflection
    inspector = reflection.Inspector(op.get_context().bind)
    return table_name in inspector.get_table_names()

def column_exists(table_name, column_name):
    from sqlalchemy.engine import reflection
    inspector = reflection.Inspector(op.get_context().bind)
    columns = inspector.get_columns(table_name)
    return any(c['name'] == column_name for c in columns)

# revision identifiers, used by Alembic.
revision = '20250908_01'
down_revision = '2025090502'
branch_labels = None
depends_on = None


def upgrade():
    """Add organization_id column to recipe_consumable table if it doesn't exist"""

    if not table_exists('recipe_consumable'):
        print("⚠️ recipe_consumable table does not exist - skipping")
        return

    if not column_exists('recipe_consumable', 'organization_id'):
        try:
            print("   Adding organization_id column to recipe_consumable...")
            op.add_column('recipe_consumable', sa.Column('organization_id', sa.Integer(), nullable=True))

            # Add foreign key constraint
            op.create_foreign_key(
                'fk_recipe_consumable_organization',
                'recipe_consumable', 
                'organization',
                ['organization_id'], 
                ['id']
            )

            print("✅ Added organization_id column and foreign key to recipe_consumable")

        except Exception as e:
            print(f"Warning: Could not add organization_id to recipe_consumable: {e}")
            # Don't re-raise, let migration continue
    else:
        print("✅ organization_id column already exists in recipe_consumable - skipping")


def downgrade():
    try:
        op.drop_index('ix_recipe_consumable_organization_id', table_name='recipe_consumable')
        op.drop_column('recipe_consumable', 'organization_id')
    except Exception as e:
        print(f"Warning: Could not remove organization_id from recipe_consumable: {e}")