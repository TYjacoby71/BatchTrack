"""0015 batch label org scope

Revision ID: 0015_batch_label_org_scope
Revises: 0014_batchbot_stack
Create Date: 2025-11-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0015_batch_label_org_scope'
down_revision = '0014_batchbot_stack'
branch_labels = None
depends_on = None


def _drop_sqlite_unique(batch_op, constraint_name, columns):
    """Remove a unique constraint from batch_op metadata during batch recreation."""
    target = tuple(columns)
    removed = False

    named = getattr(batch_op.impl, 'named_constraints', {})
    if constraint_name and constraint_name in named:
        named.pop(constraint_name, None)
        removed = True

    if not removed:
        for name, constraint in list(named.items()):
            if isinstance(constraint, sa.UniqueConstraint):
                col_names = tuple(col.name for col in constraint.columns)
                if col_names == target:
                    named.pop(name, None)
                    removed = True
                    break

    if not removed:
        for constraint in list(getattr(batch_op.impl, 'unnamed_constraints', [])):
            if isinstance(constraint, sa.UniqueConstraint):
                col_names = tuple(col.name for col in constraint.columns)
                if col_names == target:
                    batch_op.impl.unnamed_constraints.remove(constraint)
                    removed = True
                    break

    return removed


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table('batch', recreate='always') as batch_op:
            _drop_sqlite_unique(batch_op, 'batch_label_code_key', ['label_code'])
            batch_op.create_unique_constraint('uq_batch_org_label', ['organization_id', 'label_code'])
    else:
        op.drop_constraint('batch_label_code_key', 'batch', type_='unique')
        op.create_unique_constraint('uq_batch_org_label', 'batch', ['organization_id', 'label_code'])


def downgrade():
    from migrations.postgres_helpers import constraint_exists, is_postgresql

    # Remove org scoping from batch labels - revert to global unique constraint
    if constraint_exists('batch', 'uq_batch_label_code_org'):
        op.drop_constraint('uq_batch_label_code_org', 'batch', type_='unique')

    # Clean up duplicate label_code values before creating global unique constraint
    # This handles cases where the same label_code exists across different orgs
    bind = op.get_bind()
    if is_postgresql():
        # For PostgreSQL, use row_number() to identify and remove duplicates
        bind.execute(sa.text("""
            DELETE FROM batch 
            WHERE id NOT IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (PARTITION BY label_code ORDER BY id) as rn
                    FROM batch
                ) t WHERE rn = 1
            )
        """))
    else:
        # For SQLite, use a simpler approach
        bind.execute(sa.text("""
            DELETE FROM batch 
            WHERE rowid NOT IN (
                SELECT MIN(rowid) 
                FROM batch 
                GROUP BY label_code
            )
        """))

    # Now safe to create the unique constraint
    if not constraint_exists('batch', 'batch_label_code_key'):
        op.create_unique_constraint('batch_label_code_key', 'batch', ['label_code'])