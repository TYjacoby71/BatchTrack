"""Add inventory cost method toggle and valuation method fields

Revision ID: 20250922_02
Revises: 20250922_01_align_extras
Create Date: 2025-09-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250922_02'
down_revision = '20250922_01_align_extras'
branch_labels = None
depends_on = None


def upgrade():
    # Organization: add inventory cost method fields
    try:
        op.add_column('organization', sa.Column('inventory_cost_method', sa.String(length=16), nullable=True))
    except Exception:
        pass
    try:
        op.add_column('organization', sa.Column('inventory_cost_method_changed_at', sa.DateTime(), nullable=True))
    except Exception:
        pass

    # UnifiedInventoryHistory: add valuation method for audit
    try:
        op.add_column('unified_inventory_history', sa.Column('valuation_method', sa.String(length=16), nullable=True))
    except Exception:
        pass

    # Batch: snapshot cost method and timestamp
    try:
        op.add_column('batch', sa.Column('cost_method', sa.String(length=16), nullable=True))
    except Exception:
        pass
    try:
        op.add_column('batch', sa.Column('cost_method_locked_at', sa.DateTime(), nullable=True))
    except Exception:
        pass


def downgrade():
    # Reverse in safe order
    try:
        op.drop_column('batch', 'cost_method_locked_at')
    except Exception:
        pass
    try:
        op.drop_column('batch', 'cost_method')
    except Exception:
        pass
    try:
        op.drop_column('unified_inventory_history', 'valuation_method')
    except Exception:
        pass
    try:
        op.drop_column('organization', 'inventory_cost_method_changed_at')
    except Exception:
        pass
    try:
        op.drop_column('organization', 'inventory_cost_method')
    except Exception:
        pass

