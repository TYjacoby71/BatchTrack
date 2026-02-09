"""Integer base quantity columns for inventory tables.

Synopsis:
Adds base quantity columns and backfills from float quantities.

Glossary:
- Base quantity: Integer quantity stored in canonical base units.
- Base scale: Multiplier used to store fractional units.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0022_integer_base_quantities"
down_revision = "0021_recipe_lineage_backfill"
branch_labels = None
depends_on = None


BASE_SCALE = 1_000_000
COUNT_SCALE = 32
BIGINT_MAX = 9223372036854775807
BIGINT_MIN = -9223372036854775808


def _scale_sql(unit_type_expr: str) -> str:
    return f"CASE WHEN {unit_type_expr} = 'count' THEN {COUNT_SCALE} ELSE {BASE_SCALE} END"


def _clamped_bigint_sql(expr: str, *, allow_negative: bool) -> str:
    lower_bound = BIGINT_MIN if allow_negative else 0
    return (
        "CAST("
        f"LEAST(GREATEST({expr}, {lower_bound}::numeric), {BIGINT_MAX}::numeric)"
        " AS BIGINT)"
    )


def _base_quantity_sql(quantity_expr: str, *, allow_negative: bool) -> str:
    rounded_expr = f"ROUND(({quantity_expr})::numeric)"
    return _clamped_bigint_sql(rounded_expr, allow_negative=allow_negative)


def upgrade():
    op.add_column(
        "inventory_item",
        sa.Column("quantity_base", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "inventory_lot",
        sa.Column("remaining_quantity_base", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "inventory_lot",
        sa.Column("original_quantity_base", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "unified_inventory_history",
        sa.Column("quantity_change_base", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "unified_inventory_history",
        sa.Column("remaining_quantity_base", sa.BigInteger(), nullable=True),
    )

    _backfill_inventory_item_base()
    _backfill_inventory_lot_base()
    _backfill_unified_history_base()

    op.create_check_constraint(
        "check_remaining_quantity_base_non_negative",
        "inventory_lot",
        "remaining_quantity_base >= 0",
    )
    op.create_check_constraint(
        "check_original_quantity_base_positive",
        "inventory_lot",
        "original_quantity_base > 0",
    )
    op.create_check_constraint(
        "check_remaining_base_not_exceeds_original",
        "inventory_lot",
        "remaining_quantity_base <= original_quantity_base",
    )


def downgrade():
    op.drop_constraint(
        "check_remaining_base_not_exceeds_original",
        "inventory_lot",
        type_="check",
    )
    op.drop_constraint(
        "check_original_quantity_base_positive",
        "inventory_lot",
        type_="check",
    )
    op.drop_constraint(
        "check_remaining_quantity_base_non_negative",
        "inventory_lot",
        type_="check",
    )
    op.drop_column("unified_inventory_history", "remaining_quantity_base")
    op.drop_column("unified_inventory_history", "quantity_change_base")
    op.drop_column("inventory_lot", "original_quantity_base")
    op.drop_column("inventory_lot", "remaining_quantity_base")
    op.drop_column("inventory_item", "quantity_base")


def _backfill_inventory_item_base() -> None:
    quantity_base_expr = _base_quantity_sql(
        f"COALESCE(i.quantity, 0) * iu.conversion_factor * {_scale_sql('iu.unit_type')}",
        allow_negative=True,
    )
    op.execute(
        f"""
        WITH resolved_units AS (
            SELECT LOWER(u.name) AS unit_key, u.conversion_factor, u.unit_type
            FROM unit u
            UNION ALL
            SELECT LOWER(u.symbol) AS unit_key, u.conversion_factor, u.unit_type
            FROM unit u
            WHERE u.symbol IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM unit u2 WHERE LOWER(u2.name) = LOWER(u.symbol)
              )
        ),
        item_units AS (
            SELECT i.id,
                   COALESCE(ru.conversion_factor, 1) AS conversion_factor,
                   ru.unit_type
            FROM inventory_item i
            LEFT JOIN resolved_units ru
                ON ru.unit_key = LOWER(i.unit)
        )
        UPDATE inventory_item i
        SET quantity_base = {quantity_base_expr}
        FROM item_units iu
        WHERE i.id = iu.id
        """
    )


def _backfill_inventory_lot_base() -> None:
    remaining_base_expr = _base_quantity_sql(
        f"COALESCE(l.remaining_quantity, 0) * lu.conversion_factor * {_scale_sql('lu.unit_type')}",
        allow_negative=False,
    )
    original_base_expr = _base_quantity_sql(
        f"COALESCE(l.original_quantity, 0) * lu.conversion_factor * {_scale_sql('lu.unit_type')}",
        allow_negative=False,
    )
    op.execute(
        f"""
        WITH resolved_units AS (
            SELECT LOWER(u.name) AS unit_key, u.conversion_factor, u.unit_type
            FROM unit u
            UNION ALL
            SELECT LOWER(u.symbol) AS unit_key, u.conversion_factor, u.unit_type
            FROM unit u
            WHERE u.symbol IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM unit u2 WHERE LOWER(u2.name) = LOWER(u.symbol)
              )
        ),
        lot_units AS (
            SELECT l.id,
                   COALESCE(ru.conversion_factor, 1) AS conversion_factor,
                   ru.unit_type
            FROM inventory_lot l
            LEFT JOIN resolved_units ru
                ON ru.unit_key = LOWER(l.unit)
        )
        UPDATE inventory_lot l
        SET remaining_quantity_base = {remaining_base_expr},
            original_quantity_base = {original_base_expr}
        FROM lot_units lu
        WHERE l.id = lu.id
        """
    )
    op.execute(
        """
        UPDATE inventory_lot
        SET original_quantity_base = GREATEST(original_quantity_base, remaining_quantity_base, 1)
        WHERE original_quantity_base <= 0
           OR remaining_quantity_base > original_quantity_base
        """
    )


def _backfill_unified_history_base() -> None:
    quantity_change_expr = _base_quantity_sql(
        f"COALESCE(h.quantity_change, 0) * hu.conversion_factor * {_scale_sql('hu.unit_type')}",
        allow_negative=True,
    )
    remaining_expr = _base_quantity_sql(
        f"COALESCE(h.remaining_quantity, 0) * hu.conversion_factor * {_scale_sql('hu.unit_type')}",
        allow_negative=False,
    )
    op.execute(
        f"""
        WITH resolved_units AS (
            SELECT LOWER(u.name) AS unit_key, u.conversion_factor, u.unit_type
            FROM unit u
            UNION ALL
            SELECT LOWER(u.symbol) AS unit_key, u.conversion_factor, u.unit_type
            FROM unit u
            WHERE u.symbol IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM unit u2 WHERE LOWER(u2.name) = LOWER(u.symbol)
              )
        ),
        history_units AS (
            SELECT h.id,
                   COALESCE(ru.conversion_factor, 1) AS conversion_factor,
                   ru.unit_type
            FROM unified_inventory_history h
            LEFT JOIN resolved_units ru
                ON ru.unit_key = LOWER(h.unit)
        )
        UPDATE unified_inventory_history h
        SET quantity_change_base = {quantity_change_expr},
            remaining_quantity_base = CASE
                WHEN h.remaining_quantity IS NULL THEN NULL
                ELSE {remaining_expr}
            END
        FROM history_units hu
        WHERE h.id = hu.id
        """
    )
