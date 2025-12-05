
"""Remove product_group_id from recipes

Revision ID: 0019
Revises: 0018_recipe_resellable
Create Date: 2025-12-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0019'
down_revision = '0018_recipe_resellable'
branch_labels = None
depends_on = None


def upgrade():
    """Remove product_group_id column from recipe table"""
    # Check if column exists before dropping
    from alembic import op
    import sqlalchemy as sa
    from sqlalchemy import inspect
    
    connection = op.get_bind()
    inspector = inspect(connection)
    
    # Get existing columns
    columns = [col['name'] for col in inspector.get_columns('recipe')]
    
    if 'product_group_id' in columns:
        # Drop the index first if it exists
        try:
            op.drop_index('ix_recipe_product_group_id', table_name='recipe')
        except Exception:
            pass
        
        # Drop foreign key constraints that might reference this column
        try:
            fks = inspector.get_foreign_keys('recipe')
            for fk in fks:
                if 'product_group_id' in fk['constrained_columns']:
                    op.drop_constraint(fk['name'], 'recipe', type_='foreignkey')
        except Exception:
            pass
        
        # Drop the column
        op.drop_column('recipe', 'product_group_id')


def downgrade():
    """Add back product_group_id column to recipe table"""
    op.add_column('recipe', sa.Column('product_group_id', sa.INTEGER(), nullable=True))
    
    # Recreate foreign key constraint
    try:
        op.create_foreign_key('recipe_product_group_id_fkey', 'recipe', 'recipe_product_group', ['product_group_id'], ['id'])
    except Exception:
        pass  # In case recipe_product_group table doesn't exist
    
    # Recreate index
    op.create_index('ix_recipe_product_group_id', 'recipe', ['product_group_id'])
