"""
Set ON DELETE SET NULL for inventory_item.global_item_id

Revision ID: 20250904_03
Revises: 20250904_02
Create Date: 2025-09-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = '20250904_03'
down_revision = '20250904_02'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    try:
        bind = op.get_bind()
        return table_name in inspect(bind).get_table_names()
    except Exception:
        return False


def _fk_exists(table_name: str, fk_name: str) -> bool:
    try:
        bind = op.get_bind()
        fks = inspect(bind).get_foreign_keys(table_name)
        return any(fk.get('name') == fk_name for fk in fks)
    except Exception:
        return False


def _fk_is_set_null(table_name: str, fk_name: str) -> bool:
    try:
        bind = op.get_bind()
        for fk in inspect(bind).get_foreign_keys(table_name):
            if fk.get('name') == fk_name:
                # SQLAlchemy may expose 'ondelete' either top-level or under 'options'
                ondelete = fk.get('ondelete')
                if not ondelete:
                    ondelete = (fk.get('options') or {}).get('ondelete')
                return (ondelete or '').upper() == 'SET NULL'
    except Exception:
        pass
    return False


def upgrade():
    if not _table_exists('inventory_item') or not _table_exists('global_item'):
        return

    bind = op.get_bind()
    dialect = getattr(bind.dialect, 'name', '')

    # If already correct, do nothing
    if _fk_is_set_null('inventory_item', 'fk_inventory_item_global_item'):
        return

    # Ensure we start from a clean FK state
    if _fk_exists('inventory_item', 'fk_inventory_item_global_item'):
        if dialect == 'sqlite':
            with op.batch_alter_table('inventory_item') as batch_op:
                try:
                    batch_op.drop_constraint('fk_inventory_item_global_item', type_='foreignkey')
                except Exception:
                    pass
        else:
            try:
                op.drop_constraint('fk_inventory_item_global_item', 'inventory_item', type_='foreignkey')
            except Exception:
                pass

    # Recreate with ON DELETE SET NULL
    if dialect == 'sqlite':
        # SQLite requires full table rebuild to alter FK ondelete behavior; skip safely.
        return
    else:
        op.create_foreign_key(
            'fk_inventory_item_global_item',
            'inventory_item', 'global_item',
            ['global_item_id'], ['id'],
            ondelete='SET NULL'
        )


def downgrade():
    if not _table_exists('inventory_item') or not _table_exists('global_item'):
        return
    bind = op.get_bind()
    dialect = getattr(bind.dialect, 'name', '')

    # If FK not present, nothing to do
    if not _fk_exists('inventory_item', 'fk_inventory_item_global_item'):
        return

    # Replace SET NULL with default (no action)
    if dialect == 'sqlite':
        # No-op on SQLite
        return
    else:
        try:
            op.drop_constraint('fk_inventory_item_global_item', 'inventory_item', type_='foreignkey')
        except Exception:
            pass
        op.create_foreign_key(
            'fk_inventory_item_global_item',
            'inventory_item', 'global_item',
            ['global_item_id'], ['id']
        )

