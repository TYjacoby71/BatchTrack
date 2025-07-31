
"""add missing timestamp columns

Revision ID: add_missing_timestamps
Revises: f3b0e59fe9c1
Create Date: 2025-01-31 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = 'add_missing_timestamps'
down_revision = 'f3b0e59fe9c1'
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists"""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def foreign_key_exists(table_name, constraint_name):
    """Check if a foreign key constraint exists"""
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    try:
        fks = inspector.get_foreign_keys(table_name)
        return any(fk.get('name') == constraint_name for fk in fks)
    except:
        return False


def upgrade():
    print("=== Adding missing columns and constraints ===")
    
    # Create subscription_tier table if it doesn't exist
    if not table_exists('subscription_tier'):
        print("Creating subscription_tier table...")
        op.create_table('subscription_tier',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('key', sa.String(length=50), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('price_monthly', sa.Float(), nullable=True),
            sa.Column('price_yearly', sa.Float(), nullable=True),
            sa.Column('max_users', sa.Integer(), nullable=True),
            sa.Column('max_recipes', sa.Integer(), nullable=True),
            sa.Column('max_batches_per_month', sa.Integer(), nullable=True),
            sa.Column('features', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )

    # Create developer_role table if it doesn't exist  
    if not table_exists('developer_role'):
        print("Creating developer_role table...")
        op.create_table('developer_role',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )

    # Add missing columns to User table (only if they don't exist)
    if table_exists('user'):
        if not column_exists('user', 'first_name'):
            op.add_column('user', sa.Column('first_name', sa.String(length=100), nullable=True))
        if not column_exists('user', 'last_name'):
            op.add_column('user', sa.Column('last_name', sa.String(length=100), nullable=True))
        if not column_exists('user', 'phone'):
            op.add_column('user', sa.Column('phone', sa.String(length=20), nullable=True))
        if not column_exists('user', 'is_organization_owner'):
            op.add_column('user', sa.Column('is_organization_owner', sa.Boolean(), nullable=True))
        if not column_exists('user', 'updated_at'):
            op.add_column('user', sa.Column('updated_at', sa.DateTime(), nullable=True))

    # Add missing columns to Organization table  
    if table_exists('organization'):
        if not column_exists('organization', 'contact_email'):
            op.add_column('organization', sa.Column('contact_email', sa.String(length=120), nullable=True))
        if not column_exists('organization', 'subscription_tier_id'):
            op.add_column('organization', sa.Column('subscription_tier_id', sa.Integer(), nullable=True))
        if not column_exists('organization', 'updated_at'):
            op.add_column('organization', sa.Column('updated_at', sa.DateTime(), nullable=True))
        
        # Add foreign key constraint for subscription_tier_id (only if column exists and constraint doesn't)
        if column_exists('organization', 'subscription_tier_id') and table_exists('subscription_tier'):
            if not foreign_key_exists('organization', 'fk_organization_subscription_tier'):
                try:
                    op.create_foreign_key(
                        'fk_organization_subscription_tier', 
                        'organization',
                        'subscription_tier', 
                        ['subscription_tier_id'], 
                        ['id']
                    )
                except Exception as e:
                    print(f"Warning: Could not create foreign key constraint: {e}")

    # Add missing columns to Role table
    if table_exists('role'):
        if not column_exists('role', 'is_system_role'):
            op.add_column('role', sa.Column('is_system_role', sa.Boolean(), nullable=True))
        if not column_exists('role', 'created_at'):
            op.add_column('role', sa.Column('created_at', sa.DateTime(), nullable=True))
        if not column_exists('role', 'updated_at'):
            op.add_column('role', sa.Column('updated_at', sa.DateTime(), nullable=True))

    # Add missing columns to UserRoleAssignment table
    if table_exists('user_role_assignment'):
        if not column_exists('user_role_assignment', 'organization_id'):
            op.add_column('user_role_assignment', sa.Column('organization_id', sa.Integer(), nullable=True))
        if not column_exists('user_role_assignment', 'developer_role_id'):
            op.add_column('user_role_assignment', sa.Column('developer_role_id', sa.Integer(), nullable=True))
        if not column_exists('user_role_assignment', 'is_active'):
            op.add_column('user_role_assignment', sa.Column('is_active', sa.Boolean(), nullable=True))

        # Add foreign key constraints for UserRoleAssignment (only if columns exist and constraints don't)
        if column_exists('user_role_assignment', 'organization_id') and table_exists('organization'):
            if not foreign_key_exists('user_role_assignment', 'fk_user_role_assignment_organization'):
                try:
                    op.create_foreign_key(
                        'fk_user_role_assignment_organization', 
                        'user_role_assignment',
                        'organization', 
                        ['organization_id'], 
                        ['id']
                    )
                except Exception as e:
                    print(f"Warning: Could not create organization FK: {e}")
                    
        if column_exists('user_role_assignment', 'developer_role_id') and table_exists('developer_role'):
            if not foreign_key_exists('user_role_assignment', 'fk_user_role_assignment_developer_role'):
                try:
                    op.create_foreign_key(
                        'fk_user_role_assignment_developer_role', 
                        'user_role_assignment',
                        'developer_role', 
                        ['developer_role_id'], 
                        ['id']
                    )
                except Exception as e:
                    print(f"Warning: Could not create developer_role FK: {e}")

    # Add missing key column to SubscriptionTier
    if table_exists('subscription_tier'):
        if not column_exists('subscription_tier', 'key'):
            op.add_column('subscription_tier', sa.Column('key', sa.String(length=50), nullable=True))

    print("✅ Migration completed: Added missing columns and tables")


def downgrade():
    print("=== Removing added columns and tables ===")
    
    # Remove SubscriptionTier additions
    if table_exists('subscription_tier') and column_exists('subscription_tier', 'key'):
        op.drop_column('subscription_tier', 'key')

    # Remove UserRoleAssignment additions
    if table_exists('user_role_assignment'):
        try:
            if foreign_key_exists('user_role_assignment', 'fk_user_role_assignment_developer_role'):
                op.drop_constraint('fk_user_role_assignment_developer_role', 'user_role_assignment', type_='foreignkey')
            if foreign_key_exists('user_role_assignment', 'fk_user_role_assignment_organization'):
                op.drop_constraint('fk_user_role_assignment_organization', 'user_role_assignment', type_='foreignkey')
        except Exception as e:
            print(f"Warning: Could not drop foreign key constraints: {e}")
        
        if column_exists('user_role_assignment', 'is_active'):
            op.drop_column('user_role_assignment', 'is_active')
        if column_exists('user_role_assignment', 'developer_role_id'):
            op.drop_column('user_role_assignment', 'developer_role_id')
        if column_exists('user_role_assignment', 'organization_id'):
            op.drop_column('user_role_assignment', 'organization_id')

    # Remove Role additions
    if table_exists('role'):
        if column_exists('role', 'updated_at'):
            op.drop_column('role', 'updated_at')
        if column_exists('role', 'created_at'):
            op.drop_column('role', 'created_at')
        if column_exists('role', 'is_system_role'):
            op.drop_column('role', 'is_system_role')

    # Remove Organization additions
    if table_exists('organization'):
        try:
            if foreign_key_exists('organization', 'fk_organization_subscription_tier'):
                op.drop_constraint('fk_organization_subscription_tier', 'organization', type_='foreignkey')
        except Exception as e:
            print(f"Warning: Could not drop foreign key constraint: {e}")
        
        if column_exists('organization', 'updated_at'):
            op.drop_column('organization', 'updated_at')
        if column_exists('organization', 'subscription_tier_id'):
            op.drop_column('organization', 'subscription_tier_id')
        if column_exists('organization', 'contact_email'):
            op.drop_column('organization', 'contact_email')

    # Remove User additions
    if table_exists('user'):
        if column_exists('user', 'updated_at'):
            op.drop_column('user', 'updated_at')
        if column_exists('user', 'is_organization_owner'):
            op.drop_column('user', 'is_organization_owner')
        if column_exists('user', 'phone'):
            op.drop_column('user', 'phone')
        if column_exists('user', 'last_name'):
            op.drop_column('user', 'last_name')
        if column_exists('user', 'first_name'):
            op.drop_column('user', 'first_name')

    # Drop created tables
    if table_exists('developer_role'):
        op.drop_table('developer_role')
    if table_exists('subscription_tier'):
        op.drop_table('subscription_tier')

    print("✅ Downgrade completed")
