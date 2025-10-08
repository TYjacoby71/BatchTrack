"""
Add generated columns for hot batch fields (from plan_snapshot.category_extension) and indexes
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20251008_02_add_batch_hot_fields_generated_cols'
down_revision = '20251008_01_add_recipe_hot_fields_generated_cols'
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


def _add_generated_or_backfilled_column(col_name: str, sql_type: str, json_path: str):
    """Attempt to add a generated column from plan_snapshot JSON; fall back to regular column with backfill.

    json_path is like category_extension.vessel_fill_pct
    """
    if not table_exists('batch'):
        return
    if column_exists('batch', col_name):
        return

    # Try PostgreSQL generated column first
    # Build JSON path extraction: (plan_snapshot->'category_extension'->>'key')
    parts = json_path.split('.') if json_path else []
    expr = 'plan_snapshot'
    for i, part in enumerate(parts):
        if i < len(parts) - 1:
            expr += f"->'{part}'"
        else:
            expr += f"->>'{part}'"
    gen_expr = expr
    # numeric vs text
    is_text = (sql_type.lower() == 'text')
    cast_expr = '' if is_text else '::numeric'
    ddl = f"ALTER TABLE batch ADD COLUMN {col_name} {sql_type} GENERATED ALWAYS AS (({gen_expr}){cast_expr}) STORED"

    try:
        op.execute(ddl)
    except Exception:
        # Fallback: add regular column and backfill once
        with op.batch_alter_table('batch') as batch_op:
            if is_text:
                batch_op.add_column(sa.Column(col_name, sa.Text(), nullable=True))
            else:
                batch_op.add_column(sa.Column(col_name, sa.Numeric(), nullable=True))
        try:
            backfill_sql = f"""
                UPDATE batch
                SET {col_name} = NULLIF({gen_expr}, ''){cast_expr}
                WHERE plan_snapshot IS NOT NULL
+                  AND plan_snapshot ? 'category_extension'
            """
            op.execute(backfill_sql)
        except Exception:
            pass


def upgrade():
    # Numeric fields
    numeric_mappings = [
        ('vessel_fill_pct', 'numeric', 'category_extension.vessel_fill_pct'),
        ('candle_fragrance_pct', 'numeric', 'category_extension.candle_fragrance_pct'),
        ('candle_vessel_ml', 'numeric', 'category_extension.candle_vessel_ml'),
        ('soap_superfat', 'numeric', 'category_extension.soap_superfat'),
        ('soap_water_pct', 'numeric', 'category_extension.soap_water_pct'),
        ('baker_base_flour_g', 'numeric', 'category_extension.baker_base_flour_g'),
        ('baker_water_pct', 'numeric', 'category_extension.baker_water_pct'),
        ('baker_salt_pct', 'numeric', 'category_extension.baker_salt_pct'),
        ('baker_yeast_pct', 'numeric', 'category_extension.baker_yeast_pct'),
        ('cosm_emulsifier_pct', 'numeric', 'category_extension.cosm_emulsifier_pct'),
        ('cosm_preservative_pct', 'numeric', 'category_extension.cosm_preservative_pct'),
    ]
    for col_name, sql_type, json_path in numeric_mappings:
        _add_generated_or_backfilled_column(col_name, sql_type, json_path)

    # Text fields
    _add_generated_or_backfilled_column('soap_lye_type', 'text', 'category_extension.soap_lye_type')

    # Create simple btree indexes on hot fields (best effort)
    index_targets = [
        'vessel_fill_pct', 'candle_fragrance_pct', 'candle_vessel_ml',
        'soap_superfat', 'soap_water_pct', 'soap_lye_type',
        'baker_base_flour_g', 'baker_water_pct', 'baker_salt_pct', 'baker_yeast_pct',
        'cosm_emulsifier_pct', 'cosm_preservative_pct',
    ]
    for col in index_targets:
        try:
            op.create_index(f'ix_batch_{col}', 'batch', [col])
        except Exception:
            pass


def downgrade():
    # Drop indexes first
    for ix in [
        'ix_batch_vessel_fill_pct', 'ix_batch_candle_fragrance_pct', 'ix_batch_candle_vessel_ml',
        'ix_batch_soap_superfat', 'ix_batch_soap_water_pct', 'ix_batch_soap_lye_type',
        'ix_batch_baker_base_flour_g', 'ix_batch_baker_water_pct', 'ix_batch_baker_salt_pct', 'ix_batch_baker_yeast_pct',
        'ix_batch_cosm_emulsifier_pct', 'ix_batch_cosm_preservative_pct']:
        try:
            op.drop_index(ix)
        except Exception:
            pass

    # Drop columns
    drop_cols = [
        'vessel_fill_pct', 'candle_fragrance_pct', 'candle_vessel_ml',
        'soap_superfat', 'soap_water_pct', 'soap_lye_type',
        'baker_base_flour_g', 'baker_water_pct', 'baker_salt_pct', 'baker_yeast_pct',
        'cosm_emulsifier_pct', 'cosm_preservative_pct',
    ]
    for col in drop_cols:
        if column_exists('batch', col):
            try:
                with op.batch_alter_table('batch') as batch_op:
                    batch_op.drop_column(col)
            except Exception:
                pass
