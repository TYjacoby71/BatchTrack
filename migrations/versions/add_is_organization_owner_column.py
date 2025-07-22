
"""Add is_organization_owner column to users table

Revision ID: add_is_organization_owner_column
Revises: merge_all_heads_final
Create Date: 2025-01-22

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_is_organization_owner_column'
down_revision = 'merge_all_current_heads'
branch_labels = None
depends_on = None

def upgrade():
    # Add the is_organization_owner column to users table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_organization_owner', sa.Boolean(), nullable=True, default=False))
    
    # Update existing organization owners to have the flag set
    connection = op.get_bind()
    connection.execute(
        sa.text("""
            UPDATE user 
            SET is_organization_owner = 1 
            WHERE user_type = 'organization_owner'
        """)
    )

def downgrade():
    # Remove the column
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('is_organization_owner')
