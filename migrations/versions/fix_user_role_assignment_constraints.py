
"""fix user_role_assignment constraints to allow NULL role_id for developer roles

Revision ID: fix_user_role_assignment_constraints
Revises: fix_password_hash_length
Create Date: 2025-02-01 03:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'fix_user_role_constraints'
down_revision = 'fix_password_hash_length'
branch_labels = None
depends_on = None


def upgrade():
    print("=== Fixing user_role_assignment constraints ===")
    
    # Get database connection and inspector
    connection = op.get_bind()
    inspector = inspect(connection)
    
    # Check if user_role_assignment table exists
    if 'user_role_assignment' in inspector.get_table_names():
        print("   Updating user_role_assignment.role_id to allow NULL...")
        
        # Make role_id nullable for developer role assignments
        with op.batch_alter_table('user_role_assignment', schema=None) as batch_op:
            batch_op.alter_column('role_id',
                               existing_type=sa.Integer(),
                               nullable=True)
        
        print("   ✅ Updated role_id column to allow NULL values")
        
        # Add check constraint to ensure either role_id OR developer_role_id is set
        try:
            op.create_check_constraint(
                'ck_user_role_assignment_has_role',
                'user_role_assignment',
                'role_id IS NOT NULL OR developer_role_id IS NOT NULL'
            )
            print("   ✅ Added check constraint to ensure either role_id or developer_role_id is set")
        except Exception as e:
            print(f"   ⚠️  Check constraint may already exist: {e}")
    else:
        print("   ⚠️  user_role_assignment table not found - skipping")
    
    print("✅ User role assignment constraints fixed successfully")


def downgrade():
    """Revert the constraint changes"""
    print("=== Reverting user_role_assignment constraints ===")
    
    # Remove the check constraint
    try:
        op.drop_constraint('ck_user_role_assignment_has_role', 'user_role_assignment', type_='check')
    except Exception as e:
        print(f"   ⚠️  Could not drop check constraint: {e}")
    
    # Make role_id non-nullable again (this will fail if there are NULL values)
    with op.batch_alter_table('user_role_assignment', schema=None) as batch_op:
        batch_op.alter_column('role_id',
                           existing_type=sa.Integer(),
                           nullable=False)
    
    print("✅ Downgrade completed")
