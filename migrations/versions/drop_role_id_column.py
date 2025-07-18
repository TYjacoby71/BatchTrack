
"""Drop role_id column from user table

Revision ID: drop_role_id_column
Revises: zzz_final_consolidation
Create Date: 2025-07-18 23:10:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'drop_role_id_column'
down_revision = 'zzz_final_consolidation'
branch_labels = None
depends_on = None

def upgrade():
    # Use batch operations for SQLite compatibility
    with op.batch_alter_table('user', schema=None) as batch_op:
        # Try to drop the foreign key constraint first if it exists
        try:
            batch_op.drop_constraint('fk_user_role_id', type_='foreignkey')
        except:
            pass  # Constraint might not exist
        
        # Remove the role_id column if it exists
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
