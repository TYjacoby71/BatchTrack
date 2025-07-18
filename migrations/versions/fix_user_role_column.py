
"""Fix user role column removal

Revision ID: fix_user_role_column
Revises: clean_merge_final
Create Date: 2025-07-18 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'fix_user_role_column'
down_revision = 'clean_merge_final'
branch_labels = None
depends_on = None

def upgrade():
    # Check if role_id column exists and remove it
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [col['name'] for col in inspector.get_columns('user')]
    
    if 'role_id' in columns:
        # Use batch operations for SQLite compatibility
        with op.batch_alter_table('user', schema=None) as batch_op:
            # Try to drop the foreign key constraint first if it exists
            try:
                batch_op.drop_constraint('fk_user_role_id', type_='foreignkey')
            except:
                pass  # Constraint might not exist
            
            # Remove the role_id column
            batch_op.drop_column('role_id')

def downgrade():
    # Add the role_id column back if needed
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_user_role_id', 'role', ['role_id'], ['id'])
