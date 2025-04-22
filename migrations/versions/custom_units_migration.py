
"""Add custom units migration

Revision ID: custom_units_migration
Revises: b5046060fd56
Create Date: 2025-04-22 17:47:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'custom_units_migration'
down_revision = 'b5046060fd56'
branch_labels = None
depends_on = None

def upgrade():
    # Ensure is_custom column exists
    with op.batch_alter_table('unit', schema=None) as batch_op:
        if not batch_op.exists('is_custom'):
            batch_op.add_column(sa.Column('is_custom', sa.Boolean(), nullable=True))

    # Update existing custom units
    op.execute("""
        UPDATE unit 
        SET is_custom = TRUE 
        WHERE name NOT IN (
            'gram', 'kg', 'mg', 'oz', 'lb', 'ton',
            'ml', 'liter', 'tsp', 'tbsp', 'cup', 'pint', 'quart', 'gallon', 'floz', 'drop', 'dram',
            'cm', 'mm', 'inch', 'ft', 'yard', 'meter',
            'sqcm', 'sqm', 'sqinch', 'sqft', 'sqyard', 'acre',
            'cubicinch', 'cubicfoot', 'cubicyard',
            'count', 'pack', 'dozen', 'unit', 'batch', 'pair',
            'second', 'minute', 'hour', 'day'
        )
    """)

def downgrade():
    op.execute("UPDATE unit SET is_custom = FALSE WHERE is_custom = TRUE")
