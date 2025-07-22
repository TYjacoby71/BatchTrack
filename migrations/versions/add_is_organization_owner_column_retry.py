
"""add_is_organization_owner_column_retry

Revision ID: add_is_organization_owner_column_retry
Revises: 7ae741d610b4
Create Date: 2025-01-22 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_is_organization_owner_column_retry'
down_revision = '7ae741d610b4'
branch_labels = None
depends_on = None


def upgrade():
    # Check if column already exists
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [col['name'] for col in inspector.get_columns('user')]
    
    if 'is_organization_owner' not in columns:
        # Add the column directly without batch operation for SQLite
        op.add_column('user', sa.Column('is_organization_owner', sa.Boolean(), nullable=False, default=False, server_default='0'))
        
        # Update existing organization owners based on legacy user_type
        connection.execute(
            sa.text("""
                UPDATE user 
                SET is_organization_owner = 1 
                WHERE user_type = 'organization_owner'
            """)
        )
        
        # Update the user_type for organization owners to 'customer'
        connection.execute(
            sa.text("""
                UPDATE user 
                SET user_type = 'customer' 
                WHERE user_type = 'organization_owner'
            """)
        )


def downgrade():
    # Remove the column
    op.drop_column('user', 'is_organization_owner')
