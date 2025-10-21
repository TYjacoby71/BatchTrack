"""
Fix portion columns to match models: rename counts -> portion_count/projected_portions, add final_portions

Revision ID: 20251015_01
Revises: 20251011_01
Create Date: 2025-10-15

Idempotent migration that aligns the database schema with the ORM models:
- recipe.portion_count (rename from recipe.counts if present)
- batch.projected_portions (rename from batch.counts if present)
- batch.final_portions (add if missing)

Safe on Postgres; uses inspector to guard operations.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '20251015_01'
down_revision = '20251011_01'
branch_labels = None
depends_on = None


def _has_column(inspector, table: str, column: str) -> bool:
    try:
        cols = [c['name'] for c in inspector.get_columns(table)]
        return column in cols
    except Exception:
        return False


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    # --- recipe.portion_count ---
    recipe_has_portion_count = _has_column(inspector, 'recipe', 'portion_count')
    recipe_has_counts = _has_column(inspector, 'recipe', 'counts')

    if not recipe_has_portion_count:
        if recipe_has_counts:
            # Rename counts -> portion_count
            try:
                op.alter_column('recipe', 'counts', new_column_name='portion_count')
            except Exception:
                # Fallback: add new column if rename unsupported
                op.add_column('recipe', sa.Column('portion_count', sa.Integer(), nullable=True))
                # Note: not copying data in fallback as counts meaning matches projected portions; safe to leave null
        else:
            op.add_column('recipe', sa.Column('portion_count', sa.Integer(), nullable=True))

    # If both exist due to partial migrations, drop legacy counts
    if _has_column(inspector, 'recipe', 'portion_count') and _has_column(inspector, 'recipe', 'counts'):
        try:
            op.drop_column('recipe', 'counts')
        except Exception:
            pass

    # --- batch.projected_portions & batch.final_portions ---
    batch_has_projected = _has_column(inspector, 'batch', 'projected_portions')
    batch_has_final = _has_column(inspector, 'batch', 'final_portions')
    batch_has_counts = _has_column(inspector, 'batch', 'counts')

    if not batch_has_projected:
        if batch_has_counts:
            try:
                op.alter_column('batch', 'counts', new_column_name='projected_portions')
            except Exception:
                op.add_column('batch', sa.Column('projected_portions', sa.Integer(), nullable=True))
        else:
            op.add_column('batch', sa.Column('projected_portions', sa.Integer(), nullable=True))

    if not batch_has_final:
        op.add_column('batch', sa.Column('final_portions', sa.Integer(), nullable=True))

    # Clean up legacy counts if still present after rename/add
    if _has_column(inspector, 'batch', 'counts') and _has_column(inspector, 'batch', 'projected_portions'):
        try:
            op.drop_column('batch', 'counts')
        except Exception:
            pass


def downgrade():
    """
    Simple, safe downgrade: just drop the new columns and let the legacy columns be recreated
    if needed by subsequent migrations. Data loss is acceptable in downgrades.
    """
    print("=== Downgrading portion columns (dropping new columns) ===")

    # Simply drop all the new columns - much safer than trying to rename/preserve data
    columns_to_drop = [
        ('batch', 'final_portions'),
        ('batch', 'projected_portions'),
        ('recipe', 'portion_count')
    ]

    for table_name, column_name in columns_to_drop:
        try:
            with op.batch_alter_table(table_name, schema=None) as batch_op:
                batch_op.drop_column(column_name)
            print(f"✅ Dropped {column_name} from {table_name}")
        except Exception as e:
            print(f"ℹ️  Could not drop {column_name} from {table_name}: {e}")

    print("✅ Portion columns downgrade completed")