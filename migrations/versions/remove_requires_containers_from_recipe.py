
"""remove requires_containers from recipe

Revision ID: remove_requires_containers
Revises: 3d0ff5b37467
Create Date: 2025-07-02 18:13:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'remove_requires_containers'
down_revision = '3d0ff5b37467'
branch_labels = None
depends_on = None

def upgrade():
    # Remove the requires_containers column from recipe table
    with op.batch_alter_table('recipe', schema=None) as batch_op:
        batch_op.drop_column('requires_containers')

def downgrade():
    # Add back the requires_containers column
    with op.batch_alter_table('recipe', schema=None) as batch_op:
        batch_op.add_column(sa.Column('requires_containers', sa.Boolean(), nullable=True, default=False))
