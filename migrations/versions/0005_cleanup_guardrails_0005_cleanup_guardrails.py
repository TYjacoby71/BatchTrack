
"""0005 cleanup guardrails and ingredient attribute expansion

Revision ID: 0005_cleanup_guardrails
Revises: 0004_seed_presets
Create Date: 2025-10-21 20:29:06.302261

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0005_cleanup_guardrails'
down_revision = '0004_seed_presets'
branch_labels = None
depends_on = None


def upgrade():
    from migrations.postgres_helpers import is_postgresql, is_sqlite

    bind = op.get_bind()

    # Drop legacy index before renaming JSON column (succeeds even if absent)
    try:
        op.execute("DROP INDEX IF EXISTS ix_global_item_aka_gin")
    except Exception:
        pass

    # Expand global item attributes
    with op.batch_alter_table('global_item') as batch_op:
        batch_op.alter_column('aka_names', new_column_name='aliases')
        batch_op.add_column(sa.Column('recommended_usage_rate', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('recommended_fragrance_load_pct', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('inci_name', sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column('certifications', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('fatty_acid_profile', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('protein_content_pct', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('brewing_color_srm', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('brewing_potential_sg', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('brewing_diastatic_power_lintner', sa.Float(), nullable=True))
        batch_op.alter_column('is_active', server_default=None)

    if is_postgresql():
        try:
            bind.execute(sa.text(
                "CREATE INDEX IF NOT EXISTS ix_global_item_aliases_gin "
                "ON global_item USING gin ((aliases::jsonb))"
            ))
        except Exception:
            pass

    # Mirror new attributes onto inventory items
    with op.batch_alter_table('inventory_item') as batch_op:
        batch_op.add_column(sa.Column('recommended_usage_rate', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('recommended_fragrance_load_pct', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('inci_name', sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column('protein_content_pct', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('brewing_color_srm', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('brewing_potential_sg', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('brewing_diastatic_power_lintner', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('fatty_acid_profile', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('certifications', sa.JSON(), nullable=True))

    # Remove category-level attribute toggles
    with op.batch_alter_table('ingredient_category') as batch_op:
        for col in [
            'show_saponification_value',
            'show_iodine_value',
            'show_melting_point',
            'show_flash_point',
            'show_ph_value',
            'show_moisture_content',
            'show_shelf_life_days',
            'show_comedogenic_rating',
        ]:
            batch_op.drop_column(col)

    # PostgreSQL-specific performance indexes
    if is_postgresql():
        try:
            bind.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_recipe_category_data_gin ON recipe USING gin ((category_data::jsonb))'))
        except Exception:
            pass

        try:
            bind.execute(sa.text("""
                CREATE INDEX IF NOT EXISTS ix_global_item_alias_tsv ON global_item_alias 
                USING gin(to_tsvector('simple', alias))
            """))
        except Exception:
            pass

        try:
            bind.execute(sa.text('CREATE UNIQUE INDEX IF NOT EXISTS ix_product_category_lower_name ON product_category (lower(name))'))
        except Exception:
            pass


def downgrade():
    from migrations.postgres_helpers import is_postgresql, is_sqlite

    bind = op.get_bind()

    # Restore ingredient category toggles
    with op.batch_alter_table('ingredient_category') as batch_op:
        batch_op.add_column(sa.Column('show_comedogenic_rating', sa.Boolean(), nullable=True, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('show_shelf_life_days', sa.Boolean(), nullable=True, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('show_moisture_content', sa.Boolean(), nullable=True, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('show_ph_value', sa.Boolean(), nullable=True, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('show_flash_point', sa.Boolean(), nullable=True, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('show_melting_point', sa.Boolean(), nullable=True, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('show_iodine_value', sa.Boolean(), nullable=True, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('show_saponification_value', sa.Boolean(), nullable=True, server_default=sa.text('0')))

    # Remove inventory item extensions
    with op.batch_alter_table('inventory_item') as batch_op:
        batch_op.drop_column('certifications')
        batch_op.drop_column('fatty_acid_profile')
        batch_op.drop_column('brewing_diastatic_power_lintner')
        batch_op.drop_column('brewing_potential_sg')
        batch_op.drop_column('brewing_color_srm')
        batch_op.drop_column('protein_content_pct')
        batch_op.drop_column('inci_name')
        batch_op.drop_column('recommended_fragrance_load_pct')
        batch_op.drop_column('recommended_usage_rate')

    # Drop new index prior to renaming column back
    try:
        op.execute("DROP INDEX IF EXISTS ix_global_item_aliases_gin")
    except Exception:
        pass

    with op.batch_alter_table('global_item') as batch_op:
        batch_op.drop_column('brewing_diastatic_power_lintner')
        batch_op.drop_column('brewing_potential_sg')
        batch_op.drop_column('brewing_color_srm')
        batch_op.drop_column('protein_content_pct')
        batch_op.drop_column('fatty_acid_profile')
        batch_op.drop_column('certifications')
        batch_op.drop_column('inci_name')
        batch_op.drop_column('recommended_fragrance_load_pct')
        batch_op.drop_column('recommended_usage_rate')
        batch_op.alter_column('aliases', new_column_name='aka_names')
        batch_op.drop_column('is_active')

    # Drop PostgreSQL-specific indexes created in upgrade
    if is_postgresql():
        index_drops = [
            'ix_product_category_lower_name',
            'ix_global_item_alias_tsv',
            'ix_recipe_category_data_gin',
        ]

        for index_name in index_drops:
            try:
                bind.execute(sa.text(f'DROP INDEX IF EXISTS {index_name}'))
            except Exception:
                pass
    else:
        try:
            op.execute("DROP INDEX IF EXISTS ix_global_item_aliases_gin")
        except Exception:
            pass
