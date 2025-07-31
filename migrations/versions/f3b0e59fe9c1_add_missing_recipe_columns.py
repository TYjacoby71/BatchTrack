
"""add missing recipe columns

Revision ID: f3b0e59fe9c1
Revises: 132971c1d456
Create Date: 2025-07-31 19:06:39.342793

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3b0e59fe9c1'
down_revision = '132971c1d456'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add missing columns to recipe table
    Safe for production - checks if columns exist before adding
    """
    
    # Add missing columns to recipe table
    with op.batch_alter_table('recipe', schema=None) as batch_op:
        # Check and add columns only if they don't exist
        # All columns are nullable for safety during migration
        
        # Get connection to check existing columns
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        existing_columns = [col['name'] for col in inspector.get_columns('recipe')]
        
        # Only add columns that don't already exist
        if 'base_yield' not in existing_columns:
            batch_op.add_column(sa.Column('base_yield', sa.Float(), nullable=True))
        
        if 'yield_unit' not in existing_columns:
            batch_op.add_column(sa.Column('yield_unit', sa.String(length=50), nullable=True))
        
        if 'notes' not in existing_columns:
            batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))
        
        if 'tags' not in existing_columns:
            batch_op.add_column(sa.Column('tags', sa.Text(), nullable=True))
        
        if 'is_active' not in existing_columns:
            batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=True))
        
        if 'version' not in existing_columns:
            batch_op.add_column(sa.Column('version', sa.Integer(), nullable=True))

    print("✅ Recipe migration completed: All columns added safely")


def downgrade():
    """Remove the added columns - only if they exist"""
    
    # Get connection to check existing columns
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('recipe')]
    
    # Remove the added columns in reverse order, only if they exist
    with op.batch_alter_table('recipe', schema=None) as batch_op:
        if 'version' in existing_columns:
            batch_op.drop_column('version')
        
        if 'is_active' in existing_columns:
            batch_op.drop_column('is_active')
        
        if 'tags' in existing_columns:
            batch_op.drop_column('tags')
        
        if 'notes' in existing_columns:
            batch_op.drop_column('notes')
        
        if 'yield_unit' in existing_columns:
            batch_op.drop_column('yield_unit')
        
        if 'base_yield' in existing_columns:
            batch_op.drop_column('base_yield')
