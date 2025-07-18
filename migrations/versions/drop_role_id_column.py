
"""Drop role_id column from user table

Revision ID: drop_role_id_column
Revises: zzz_final_consolidation
Create Date: 2025-07-18 23:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'drop_role_id_column'
down_revision = 'zzz_final_consolidation'
branch_labels = None
depends_on = None

def upgrade():
    # Get connection and inspector to check current table structure
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Get existing columns and foreign keys
    user_columns = [col['name'] for col in inspector.get_columns('user')]
    user_foreign_keys = inspector.get_foreign_keys('user')
    
    # Only proceed if role_id column exists
    if 'role_id' in user_columns:
        # Use batch operations for SQLite compatibility
        with op.batch_alter_table('user', schema=None) as batch_op:
            # Try to drop any foreign key constraints related to role_id
            for fk in user_foreign_keys:
                if 'role_id' in fk.get('constrained_columns', []) and fk.get('name'):
                    try:
                        batch_op.drop_constraint(fk['name'], type_='foreignkey')
                    except:
                        pass  # Constraint might not exist or already dropped
            
            # Remove the role_id column
            try:
                batch_op.drop_column('role_id')
            except:
                pass  # Column might not exist

def downgrade():
    # Add the role_id column back if needed
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role_id', sa.Integer(), nullable=True))
        try:
            batch_op.create_foreign_key('fk_user_role_id', 'role', ['role_id'], ['id'])
        except:
            pass
