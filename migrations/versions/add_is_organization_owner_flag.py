
"""Add is_organization_owner flag to users

Revision ID: add_is_organization_owner_flag
Revises: consolidate_all_heads_final
Create Date: 2025-01-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers
revision = 'add_is_organization_owner_flag'
down_revision = 'consolidate_all_heads_final'
branch_labels = None
depends_on = None

def upgrade():
    # Add the new column
    op.add_column('user', sa.Column('is_organization_owner', sa.Boolean(), default=False))
    
    # Update existing organization owner users
    connection = op.get_bind()
    
    # Set flag for users who currently have user_type='organization_owner'
    connection.execute(text("""
        UPDATE user 
        SET is_organization_owner = 1 
        WHERE user_type = 'organization_owner'
    """))
    
    # Update user_type for organization owners to 'customer'
    connection.execute(text("""
        UPDATE user 
        SET user_type = 'customer' 
        WHERE user_type = 'organization_owner'
    """))

def downgrade():
    # Restore organization_owner user_type
    connection = op.get_bind()
    connection.execute(text("""
        UPDATE user 
        SET user_type = 'organization_owner' 
        WHERE is_organization_owner = 1
    """))
    
    # Drop the column
    op.drop_column('user', 'is_organization_owner')
