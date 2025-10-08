"""
Add generated columns for hot recipe fields and basic indexes
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20251008_01_add_recipe_hot_fields_generated_cols'
down_revision = '20251006_02_add_product_category_ui_config'
branch_labels = None
depends_on = None


def table_exists(table_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def _add_generated_or_backfilled_column(col_name: str, sql_type: str, json_key: str, cast: str | None = None):
    """Attempt to add a generated/stored column; fall back to nullable column with backfill.

    Uses PostgreSQL syntax for generated columns. If it fails (e.g., SQLite),
    add a nullable column and best-effort backfill from JSON.
    """
    if not table_exists('recipe'):
        return
    if column_exists('recipe', col_name):
        return

    # Try PostgreSQL generated column first
    cast_expr = f"::{cast}" if cast else ""
    gen_expr = f"(category_data->>'{json_key}'){cast_expr}"
    ddl = f"ALTER TABLE recipe ADD COLUMN {col_name} {sql_type} GENERATED ALWAYS AS ({gen_expr}) STORED"

    try:
        op.execute(ddl)
    except Exception:
        # Fallback: add regular column and backfill once
        with op.batch_alter_table('recipe') as batch_op:
            if sql_type.lower() == 'text':
                batch_op.add_column(sa.Column(col_name, sa.Text(), nullable=True))
            else:
                batch_op.add_column(sa.Column(col_name, sa.Numeric(), nullable=True))
        try:
            # Best-effort backfill (PostgreSQL JSON syntax). Ignore errors on non-PG backends.
            backfill_sql = (
                f"UPDATE recipe SET {col_name} = "
                f"NULLIF(category_data->>'{json_key}', '')"
            )
            if sql_type.lower() != 'text':
                backfill_sql += "::numeric"
            backfill_sql += " WHERE category_data IS NOT NULL"
            op.execute(backfill_sql)
        except Exception:
            pass


def upgrade():
    # Numeric fields
    numeric_fields = [
        ('soap_superfat', 'numeric', 'soap_superfat', 'numeric'),
        ('soap_water_pct', 'numeric', 'soap_water_pct', 'numeric'),
        ('candle_fragrance_pct', 'numeric', 'candle_fragrance_pct', 'numeric'),
        ('candle_vessel_ml', 'numeric', 'candle_vessel_ml', 'numeric'),
        ('vessel_fill_pct', 'numeric', 'vessel_fill_pct', 'numeric'),
        ('baker_base_flour_g', 'numeric', 'baker_base_flour_g', 'numeric'),
        ('baker_water_pct', 'numeric', 'baker_water_pct', 'numeric'),
        ('baker_salt_pct', 'numeric', 'baker_salt_pct', 'numeric'),
        ('baker_yeast_pct', 'numeric', 'baker_yeast_pct', 'numeric'),
        ('cosm_emulsifier_pct', 'numeric', 'cosm_emulsifier_pct', 'numeric'),
        ('cosm_preservative_pct', 'numeric', 'cosm_preservative_pct', 'numeric'),
    ]
    for col_name, sql_type, json_key, cast in numeric_fields:
        _add_generated_or_backfilled_column(col_name, sql_type, json_key, cast)

    # Text fields
    _add_generated_or_backfilled_column('soap_lye_type', 'text', 'soap_lye_type', None)

    # Create simple btree indexes on hot fields (best effort)
    index_targets = [
        'soap_superfat', 'soap_water_pct', 'soap_lye_type',
        'candle_fragrance_pct', 'candle_vessel_ml', 'vessel_fill_pct',
        'baker_base_flour_g', 'baker_water_pct', 'baker_salt_pct', 'baker_yeast_pct',
        'cosm_emulsifier_pct', 'cosm_preservative_pct',
    ]
    for col in index_targets:
        try:
            op.create_index(f'ix_recipe_{col}', 'recipe', [col])
        except Exception:
            pass


def downgrade():
    # Drop indexes first
    for ix in [
        'ix_recipe_soap_superfat', 'ix_recipe_soap_water_pct', 'ix_recipe_soap_lye_type',
        'ix_recipe_candle_fragrance_pct', 'ix_recipe_candle_vessel_ml', 'ix_recipe_vessel_fill_pct',
        'ix_recipe_baker_base_flour_g', 'ix_recipe_baker_water_pct', 'ix_recipe_baker_salt_pct', 'ix_recipe_baker_yeast_pct',
        'ix_recipe_cosm_emulsifier_pct', 'ix_recipe_cosm_preservative_pct']:
        try:
            op.drop_index(ix)
        except Exception:
            pass

    # Drop columns (best effort)
    drop_cols = [
        'soap_superfat', 'soap_water_pct', 'soap_lye_type',
        'candle_fragrance_pct', 'candle_vessel_ml', 'vessel_fill_pct',
        'baker_base_flour_g', 'baker_water_pct', 'baker_salt_pct', 'baker_yeast_pct',
        'cosm_emulsifier_pct', 'cosm_preservative_pct',
    ]
    for col in drop_cols:
        if column_exists('recipe', col):
            try:
                with op.batch_alter_table('recipe') as batch_op:
                    batch_op.drop_column(col)
            except Exception:
                pass
