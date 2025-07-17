
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
    
    # Use batch operations for SQLite compatibility
    with op.batch_alter_table('role', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_system_role', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('created_by', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_role_created_by', 'user', ['created_by'], ['id'])
        batch_op.create_foreign_key('fk_role_organization', 'organization', ['organization_id'], ['id'])
        batch_op.create_unique_constraint('unique_role_name_org', ['name', 'organization_id'])
    
    # Add new column to permission table
    with op.batch_alter_table('permission', schema=None) as batch_op:
        batch_op.add_column(sa.Column('required_subscription_tier', sa.String(length=32), nullable=True))
    
    # Remove deprecated columns from user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('role_id')
        batch_op.drop_column('subscription_class')
        batch_op.drop_column('is_owner')

def downgrade():
    # Add back deprecated columns
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_owner', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('subscription_class', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('role_id', sa.Integer(), nullable=False))
    
    # Remove new columns from permission table
    with op.batch_alter_table('permission', schema=None) as batch_op:
        batch_op.drop_column('required_subscription_tier')
    
    # Remove constraints and columns from role table
    with op.batch_alter_table('role', schema=None) as batch_op:
        batch_op.drop_constraint('unique_role_name_org', type_='unique')
        batch_op.drop_constraint('fk_role_organization', type_='foreignkey')
        batch_op.drop_constraint('fk_role_created_by', type_='foreignkey')
        batch_op.drop_column('organization_id')
        batch_op.drop_column('created_by')
        batch_op.drop_column('is_system_role')
    
    # Drop user_role_assignment table
    op.drop_table('user_role_assignment')
