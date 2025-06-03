
"""Add unique constraint to recipe label_prefix

Revision ID: add_unique_label_prefix
Revises: bef17a1c97ee
Create Date: 2025-06-03 18:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_unique_label_prefix'
down_revision = 'bef17a1c97ee'
branch_labels = None
depends_on = None

def upgrade():
    # First, update any NULL label_prefix values to avoid constraint violation
    op.execute("UPDATE recipe SET label_prefix = 'BTH' WHERE label_prefix IS NULL OR label_prefix = ''")
    
    # Make label_prefix NOT NULL
    op.alter_column('recipe', 'label_prefix',
               existing_type=sa.VARCHAR(length=8),
               nullable=False)
    
    # Add unique constraint
    op.create_unique_constraint('uq_recipe_label_prefix', 'recipe', ['label_prefix'])

def downgrade():
    # Remove unique constraint
    op.drop_constraint('uq_recipe_label_prefix', 'recipe', type_='unique')
    
    # Make label_prefix nullable again
    op.alter_column('recipe', 'label_prefix',
               existing_type=sa.VARCHAR(length=8),
               nullable=True)
