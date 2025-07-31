
"""add missing timestamp columns

Revision ID: add_missing_timestamps
Revises: f3b0e59fe9c1
Create Date: 2025-01-31 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'add_missing_timestamps'
down_revision = 'f3b0e59fe9c1'
branch_labels = None
depends_on = None

def upgrade():
    """Add missing timestamp columns to User and Organization tables"""
    
    # Add missing columns to User table
    with op.batch_alter_table('user', schema=None) as batch_op:
        # Add missing user columns that the seeder expects
        batch_op.add_column(sa.Column('first_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('last_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('phone', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('is_organization_owner', sa.Boolean(), nullable=True, default=False))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        
        # Note: created_at already exists in the base migration

    # Add missing columns to Organization table  
    with op.batch_alter_table('organization', schema=None) as batch_op:
        batch_op.add_column(sa.Column('contact_email', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('subscription_tier_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
    
    # Add foreign key constraint for subscription_tier_id
    with op.batch_alter_table('organization', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_organization_subscription_tier', 
            'subscription_tier', 
            ['subscription_tier_id'], 
            ['id']
        )

    # Add missing columns to Role table
    with op.batch_alter_table('role', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_system_role', sa.Boolean(), nullable=True, default=False))
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

    # Add missing columns to UserRoleAssignment table
    with op.batch_alter_table('user_role_assignment', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('developer_role_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=True, default=True))

    # Add foreign key constraints for UserRoleAssignment
    with op.batch_alter_table('user_role_assignment', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_user_role_assignment_organization', 
            'organization', 
            ['organization_id'], 
            ['id']
        )
        batch_op.create_foreign_key(
            'fk_user_role_assignment_developer_role', 
            'developer_role', 
            ['developer_role_id'], 
            ['id']
        )

    # Add missing key column to SubscriptionTier
    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        batch_op.add_column(sa.Column('key', sa.String(length=50), nullable=True))

    print("✅ Migration completed: Added missing timestamp and relationship columns")

def downgrade():
    """Remove the added columns"""
    
    # Remove SubscriptionTier additions
    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        batch_op.drop_column('key')

    # Remove UserRoleAssignment additions
    with op.batch_alter_table('user_role_assignment', schema=None) as batch_op:
        batch_op.drop_constraint('fk_user_role_assignment_developer_role', type_='foreignkey')
        batch_op.drop_constraint('fk_user_role_assignment_organization', type_='foreignkey')
        batch_op.drop_column('is_active')
        batch_op.drop_column('developer_role_id')
        batch_op.drop_column('organization_id')

    # Remove Role additions
    with op.batch_alter_table('role', schema=None) as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')
        batch_op.drop_column('is_system_role')

    # Remove Organization additions
    with op.batch_alter_table('organization', schema=None) as batch_op:
        batch_op.drop_constraint('fk_organization_subscription_tier', type_='foreignkey')
        batch_op.drop_column('updated_at')
        batch_op.drop_column('subscription_tier_id')
        batch_op.drop_column('contact_email')

    # Remove User additions
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('is_organization_owner')
        batch_op.drop_column('phone')
        batch_op.drop_column('last_name')
        batch_op.drop_column('first_name')
