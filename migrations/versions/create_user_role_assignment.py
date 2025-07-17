
"""Create user role assignment table

Revision ID: create_user_role_assignment
Revises: f6a9b50d9a17
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'create_user_role_assignment'
down_revision = 'f6a9b50d9a17'
branch_labels = None
depends_on = None

def upgrade():
    # Create user_role_assignment table
    op.create_table('user_role_assignment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('assigned_by', sa.Integer(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['assigned_by'], ['user.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
        sa.ForeignKeyConstraint(['role_id'], ['role.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'role_id', 'organization_id', name='unique_user_role_org')
    )
    
    # Add new columns to role table
    op.add_column('role', sa.Column('is_system_role', sa.Boolean(), nullable=True))
    op.add_column('role', sa.Column('created_by', sa.Integer(), nullable=True))
    op.add_column('role', sa.Column('organization_id', sa.Integer(), nullable=True))
    
    # Add foreign key constraints
    op.create_foreign_key(None, 'role', 'user', ['created_by'], ['id'])
    op.create_foreign_key(None, 'role', 'organization', ['organization_id'], ['id'])
    
    # Add unique constraint for role name per organization
    op.create_unique_constraint('unique_role_name_org', 'role', ['name', 'organization_id'])
    
    # Add new column to permission table
    op.add_column('permission', sa.Column('required_subscription_tier', sa.String(length=32), nullable=True))
    
    # Remove deprecated columns from user table
    op.drop_column('user', 'role_id')
    op.drop_column('user', 'subscription_class')
    op.drop_column('user', 'is_owner')

def downgrade():
    # Add back deprecated columns
    op.add_column('user', sa.Column('is_owner', sa.Boolean(), nullable=True))
    op.add_column('user', sa.Column('subscription_class', sa.String(length=32), nullable=True))
    op.add_column('user', sa.Column('role_id', sa.Integer(), nullable=False))
    
    # Remove new columns from permission table
    op.drop_column('permission', 'required_subscription_tier')
    
    # Remove constraints and columns from role table
    op.drop_constraint('unique_role_name_org', 'role', type_='unique')
    op.drop_column('role', 'organization_id')
    op.drop_column('role', 'created_by')
    op.drop_column('role', 'is_system_role')
    
    # Drop user_role_assignment table
    op.drop_table('user_role_assignment')
