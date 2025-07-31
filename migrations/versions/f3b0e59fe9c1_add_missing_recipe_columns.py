"""add missing recipe columns

Revision ID: f3b0e59fe9c1
Revises: 132971c1d456
Create Date: 2025-07-31 19:06:39.342793

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3b0e59fe9c1'
down_revision = '132971c1d456'
branch_labels = None
depends_on = None


def upgrade():
    # Add missing columns to recipe table
    with op.batch_alter_table('recipe', schema=None) as batch_op:
        # Add the missing columns from the model definition
        batch_op.add_column(sa.Column('base_yield', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('yield_unit', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('tags', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('version', sa.Integer(), nullable=True))


def downgrade():
    # Remove the added columns
    with op.batch_alter_table('recipe', schema=None) as batch_op:
        batch_op.drop_column('version')
        batch_op.drop_column('is_active')
        batch_op.drop_column('tags')
        batch_op.drop_column('notes')
        batch_op.drop_column('yield_unit')
        batch_op.drop_column('base_yield')
