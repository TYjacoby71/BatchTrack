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
    if constraint_exists('batch', 'uq_batch_org_label'):
        op.drop_constraint('uq_batch_org_label', 'batch', type_='unique')

    # Clean up duplicate label_code values before creating global unique constraint
    # This handles cases where the same label_code exists across different orgs
    bind = op.get_bind()
    if is_postgresql():
        # First, identify batches to be deleted (duplicates)
        duplicates_to_delete = bind.execute(sa.text("""
            SELECT id FROM batch 
            WHERE id NOT IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (PARTITION BY label_code ORDER BY id) as rn
                    FROM batch
                ) t WHERE rn = 1
            )
        """)).fetchall()

        if duplicates_to_delete:
            batch_ids = [str(row[0]) for row in duplicates_to_delete]
            batch_ids_str = ','.join(batch_ids)

            # Delete ALL dependent records first to avoid foreign key violations
            # Order matters - delete from most dependent to least dependent

            # 1. Delete from tables that reference batch_consumable, batch_ingredient, batch_container
            bind.execute(sa.text(f"""
                DELETE FROM batch_inventory_log WHERE batch_id IN ({batch_ids_str})
            """))

            # 2. Delete extra batch records (they reference the main batch tables)
            bind.execute(sa.text(f"""
                DELETE FROM extra_batch_consumable WHERE batch_id IN ({batch_ids_str})
            """))
            bind.execute(sa.text(f"""
                DELETE FROM extra_batch_ingredient WHERE batch_id IN ({batch_ids_str})
            """))
            bind.execute(sa.text(f"""
                DELETE FROM extra_batch_container WHERE batch_id IN ({batch_ids_str})
            """))

            # 3. Delete batch timers
            bind.execute(sa.text(f"""
                DELETE FROM batch_timer WHERE batch_id IN ({batch_ids_str})
            """))

            # 4. Delete main batch component records
            bind.execute(sa.text(f"""
                DELETE FROM batch_consumable WHERE batch_id IN ({batch_ids_str})
            """))
            bind.execute(sa.text(f"""
                DELETE FROM batch_ingredient WHERE batch_id IN ({batch_ids_str})
            """))
            bind.execute(sa.text(f"""
                DELETE FROM batch_container WHERE batch_id IN ({batch_ids_str})
            """))

            # 5. Update inventory_history references to NULL (optional FK)
            bind.execute(sa.text(f"""
                UPDATE inventory_history SET batch_id = NULL WHERE batch_id IN ({batch_ids_str})
            """))
            bind.execute(sa.text(f"""
                UPDATE inventory_history SET used_for_batch_id = NULL WHERE used_for_batch_id IN ({batch_ids_str})
            """))

            # 6. Update inventory_item references to NULL (optional FK)
            bind.execute(sa.text(f"""
                UPDATE inventory_item SET batch_id = NULL WHERE batch_id IN ({batch_ids_str})
            """))

            # 7. Update product_sku references to NULL (optional FK)  
            bind.execute(sa.text(f"""
                UPDATE product_sku SET batch_id = NULL WHERE batch_id IN ({batch_ids_str})
            """))

            # 8. Now safe to delete the duplicate batch records
            bind.execute(sa.text(f"""
                DELETE FROM batch WHERE id IN ({batch_ids_str})
            """))
    else:
        # For SQLite, use a simpler approach with proper cleanup
        duplicates = bind.execute(sa.text("""
            SELECT rowid FROM batch 
            WHERE rowid NOT IN (
                SELECT MIN(rowid) 
                FROM batch 
                GROUP BY label_code
            )
        """)).fetchall()

        if duplicates:
            duplicate_ids = [str(row[0]) for row in duplicates]
            duplicate_ids_str = ','.join(duplicate_ids)

            # Clean up ALL dependent records first (SQLite version)
            batch_ids_subquery = f"SELECT id FROM batch WHERE rowid IN ({duplicate_ids_str})"

            # 1. Delete batch logs
            bind.execute(sa.text(f"""
                DELETE FROM batch_inventory_log WHERE batch_id IN ({batch_ids_subquery})
            """))

            # 2. Delete extra batch records
            bind.execute(sa.text(f"""
                DELETE FROM extra_batch_consumable WHERE batch_id IN ({batch_ids_subquery})
            """))
            bind.execute(sa.text(f"""
                DELETE FROM extra_batch_ingredient WHERE batch_id IN ({batch_ids_subquery})
            """))
            bind.execute(sa.text(f"""
                DELETE FROM extra_batch_container WHERE batch_id IN ({batch_ids_subquery})
            """))

            # 3. Delete batch timers
            bind.execute(sa.text(f"""
                DELETE FROM batch_timer WHERE batch_id IN ({batch_ids_subquery})
            """))

            # 4. Delete main batch component records
            bind.execute(sa.text(f"""
                DELETE FROM batch_consumable WHERE batch_id IN ({batch_ids_subquery})
            """))
            bind.execute(sa.text(f"""
                DELETE FROM batch_ingredient WHERE batch_id IN ({batch_ids_subquery})
            """))
            bind.execute(sa.text(f"""
                DELETE FROM batch_container WHERE batch_id IN ({batch_ids_subquery})
            """))

            # 5. Update references to NULL
            bind.execute(sa.text(f"""
                UPDATE inventory_history SET batch_id = NULL WHERE batch_id IN ({batch_ids_subquery})
            """))
            bind.execute(sa.text(f"""
                UPDATE inventory_history SET used_for_batch_id = NULL WHERE used_for_batch_id IN ({batch_ids_subquery})
            """))
            bind.execute(sa.text(f"""
                UPDATE inventory_item SET batch_id = NULL WHERE batch_id IN ({batch_ids_subquery})
            """))
            bind.execute(sa.text(f"""
                UPDATE product_sku SET batch_id = NULL WHERE batch_id IN ({batch_ids_subquery})
            """))

            # 6. Now delete the duplicate batches
            bind.execute(sa.text(f"""
                DELETE FROM batch WHERE rowid IN ({duplicate_ids_str})
            """))

    # Now safe to create the unique constraint
    if not constraint_exists('batch', 'batch_label_code_key'):
        op.create_unique_constraint('batch_label_code_key', 'batch', ['label_code'])