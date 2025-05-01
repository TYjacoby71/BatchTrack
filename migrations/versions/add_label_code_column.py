
"""add label code column

Revision ID: add_label_code_column
Revises: d3417cb6cf8c
Create Date: 2025-05-01 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_label_code_column'
down_revision = 'd3417cb6cf8c'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('batch', sa.Column('label_code', sa.String(32), unique=True))

def downgrade():
    op.drop_column('batch', 'label_code')
