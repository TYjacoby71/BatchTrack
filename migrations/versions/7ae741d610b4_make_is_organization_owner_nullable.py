
"""make_is_organization_owner_nullable

Revision ID: 7ae741d610b4
Revises: zzz_final_merge_all_heads
Create Date: 2025-07-22 23:15:33.918078

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7ae741d610b4'
down_revision = 'zzz_final_merge_all_heads'
branch_labels = None
depends_on = None


def upgrade():
    # Add the is_organization_owner column if it doesn't exist
    connection = op.get_bind()
    
    # Check if column already exists
    inspector = sa.inspect(connection)
    columns = [col['name'] for col in inspector.get_columns('user')]
    
    if 'is_organization_owner' not in columns:
        with op.batch_alter_table('user', schema=None) as batch_op:
            batch_op.add_column(sa.Column('is_organization_owner', sa.Boolean(), 
                                         nullable=False, default=False, server_default='0'))
        
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
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('is_organization_owner')
