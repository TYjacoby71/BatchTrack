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
    op.execute(
        f"""
        WITH resolved_units AS (
            SELECT u.name AS unit_key, u.conversion_factor, u.unit_type
            FROM unit u
            UNION ALL
            SELECT u.symbol AS unit_key, u.conversion_factor, u.unit_type
            FROM unit u
            WHERE u.symbol IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM unit u2 WHERE u2.name = u.symbol)
        )
        UPDATE inventory_item i
        SET quantity_base = CAST(
            ROUND(
                COALESCE(i.quantity, 0) * ru.conversion_factor *
                CASE WHEN ru.unit_type = 'count' THEN {COUNT_SCALE} ELSE {BASE_SCALE} END
            ) AS BIGINT
        )
        FROM resolved_units ru
        WHERE ru.unit_key = i.unit
        """
    )


def _backfill_inventory_lot_base() -> None:
    op.execute(
        f"""
        WITH resolved_units AS (
            SELECT u.name AS unit_key, u.conversion_factor, u.unit_type
            FROM unit u
            UNION ALL
            SELECT u.symbol AS unit_key, u.conversion_factor, u.unit_type
            FROM unit u
            WHERE u.symbol IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM unit u2 WHERE u2.name = u.symbol)
        )
        UPDATE inventory_lot l
        SET remaining_quantity_base = CAST(
                ROUND(
                    COALESCE(l.remaining_quantity, 0) * ru.conversion_factor *
                    CASE WHEN ru.unit_type = 'count' THEN {COUNT_SCALE} ELSE {BASE_SCALE} END
                ) AS BIGINT
            ),
            original_quantity_base = CAST(
                ROUND(
                    COALESCE(l.original_quantity, 0) * ru.conversion_factor *
                    CASE WHEN ru.unit_type = 'count' THEN {COUNT_SCALE} ELSE {BASE_SCALE} END
                ) AS BIGINT
            )
        FROM resolved_units ru
        WHERE ru.unit_key = l.unit
        """
    )


def _backfill_unified_history_base() -> None:
    op.execute(
        f"""
        WITH resolved_units AS (
            SELECT u.name AS unit_key, u.conversion_factor, u.unit_type
            FROM unit u
            UNION ALL
            SELECT u.symbol AS unit_key, u.conversion_factor, u.unit_type
            FROM unit u
            WHERE u.symbol IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM unit u2 WHERE u2.name = u.symbol)
        )
        UPDATE unified_inventory_history h
        SET quantity_change_base = CAST(
                ROUND(
                    COALESCE(h.quantity_change, 0) * ru.conversion_factor *
                    CASE WHEN ru.unit_type = 'count' THEN {COUNT_SCALE} ELSE {BASE_SCALE} END
                ) AS BIGINT
            ),
            remaining_quantity_base = CASE
                WHEN h.remaining_quantity IS NULL THEN NULL
                ELSE CAST(
                    ROUND(
                        COALESCE(h.remaining_quantity, 0) * ru.conversion_factor *
                        CASE WHEN ru.unit_type = 'count' THEN {COUNT_SCALE} ELSE {BASE_SCALE} END
                    ) AS BIGINT
                )
            END
        FROM resolved_units ru
        WHERE ru.unit_key = h.unit
        """
    )
