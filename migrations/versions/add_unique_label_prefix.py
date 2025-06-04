
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
    
    # Use batch operations for SQLite compatibility
    with op.batch_alter_table('recipe', schema=None) as batch_op:
        # Make label_prefix NOT NULL
        batch_op.alter_column('label_prefix',
                   existing_type=sa.VARCHAR(length=8),
                   nullable=False)
        
        # Add unique constraint
        batch_op.create_unique_constraint('uq_recipe_label_prefix', ['label_prefix'])

def downgrade():
    # Use batch operations for SQLite compatibility
    with op.batch_alter_table('recipe', schema=None) as batch_op:
        # Remove unique constraint
        batch_op.drop_constraint('uq_recipe_label_prefix', type_='unique')
        
        # Make label_prefix nullable again
        batch_op.alter_column('label_prefix',
                   existing_type=sa.VARCHAR(length=8),
                   nullable=True)
