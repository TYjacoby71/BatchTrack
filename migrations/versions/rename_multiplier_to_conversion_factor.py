
"""Rename multiplier to conversion_factor in CustomUnitMapping

Revision ID: rename_multiplier_cf
Revises: aa271449bf33
Create Date: 2025-07-19 00:54:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'rename_multiplier_cf'
down_revision = 'aa271449bf33'
branch_labels = None
depends_on = None

def upgrade():
    # Rename multiplier column to conversion_factor
    with op.batch_alter_table('custom_unit_mapping', schema=None) as batch_op:
        batch_op.alter_column('multiplier', new_column_name='conversion_factor')

def downgrade():
    # Rename conversion_factor column back to multiplier
    with op.batch_alter_table('custom_unit_mapping', schema=None) as batch_op:
        batch_op.alter_column('conversion_factor', new_column_name='multiplier')
