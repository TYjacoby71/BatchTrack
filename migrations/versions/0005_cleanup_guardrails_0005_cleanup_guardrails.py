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
    from migrations.postgres_helpers import is_postgresql, is_sqlite, safe_add_column

    bind = op.get_bind()

    # Drop legacy index before renaming JSON column (succeeds even if absent)
    try:
        op.execute("DROP INDEX IF EXISTS ix_global_item_aka_gin")
    except Exception:
        pass

    # Expand global item attributes  
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        columns = [col['name'] for col in inspector.get_columns('global_item')]
        if 'aka_names' in columns:
            with op.batch_alter_table('global_item') as batch_op:
                batch_op.alter_column('aka_names', new_column_name='aliases')
        elif 'aliases' not in columns:
            # Neither column exists - this is unexpected 
            print("⚠️  Neither 'aka_names' nor 'aliases' column found in global_item table")
    except Exception as e:
        print(f"⚠️  Could not rename aka_names column: {e}")

    # Add new columns to global_item for enhanced ingredient data (safely)
    safe_add_column('global_item', sa.Column('fatty_acid_profile', sa.JSON()))
    safe_add_column('global_item', sa.Column('brewing_diastatic_power_lintner', sa.Float()))
    safe_add_column('global_item', sa.Column('brewing_potential_sg', sa.Float()))
    safe_add_column('global_item', sa.Column('brewing_color_srm', sa.Float()))
    safe_add_column('global_item', sa.Column('protein_content_pct', sa.Float()))
    safe_add_column('global_item', sa.Column('certifications', sa.JSON()))
    safe_add_column('global_item', sa.Column('inci_name', sa.String(256)))
    safe_add_column('global_item', sa.Column('recommended_fragrance_load_pct', sa.Float()))
    safe_add_column('global_item', sa.Column('recommended_usage_rate', sa.String(128)))
    safe_add_column('global_item', sa.Column('is_active_ingredient', sa.Boolean()))

    # Update existing NULL values to False before setting NOT NULL constraint
    op.execute("UPDATE global_item SET is_active_ingredient = FALSE WHERE is_active_ingredient IS NULL")
    
    # Now set the column to NOT NULL
    with op.batch_alter_table('global_item') as batch_op:
        batch_op.alter_column('is_active_ingredient', server_default=None, nullable=False)
        batch_op.alter_column('recommended_usage_rate',
               existing_type=sa.VARCHAR(length=128),
               type_=sa.String(length=64),
               existing_nullable=True)
        batch_op.alter_column('recommended_fragrance_load_pct',
               existing_type=sa.Float(),
               type_=sa.String(length=64),
               existing_nullable=True)

    if is_postgresql():
        try:
            bind.execute(sa.text(
                "CREATE INDEX IF NOT EXISTS ix_global_item_aliases_gin "
                "ON global_item USING gin ((aliases::jsonb))"
            ))
        except Exception:
            pass

    # Mirror new attributes onto inventory items
    # Add same columns to inventory_item for backwards compatibility (safely)
    safe_add_column('inventory_item', sa.Column('certifications', sa.JSON()))
    safe_add_column('inventory_item', sa.Column('fatty_acid_profile', sa.JSON()))
    safe_add_column('inventory_item', sa.Column('brewing_diastatic_power_lintner', sa.Float()))
    safe_add_column('inventory_item', sa.Column('brewing_potential_sg', sa.Float()))
    safe_add_column('inventory_item', sa.Column('brewing_color_srm', sa.Float()))
    safe_add_column('inventory_item', sa.Column('protein_content_pct', sa.Float()))
    safe_add_column('inventory_item', sa.Column('inci_name', sa.String(256)))
    safe_add_column('inventory_item', sa.Column('recommended_fragrance_load_pct', sa.Float()))
    safe_add_column('inventory_item', sa.Column('recommended_usage_rate', sa.String(128)))

    # Now alter the column types for inventory_item
    with op.batch_alter_table('inventory_item') as batch_op:
        batch_op.alter_column('recommended_usage_rate',
               existing_type=sa.VARCHAR(length=128),
               type_=sa.String(length=64),
               existing_nullable=True)
        batch_op.alter_column('recommended_fragrance_load_pct',
               existing_type=sa.Float(),
               type_=sa.String(length=64),
               existing_nullable=True)

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
    from migrations.postgres_helpers import is_postgresql, is_sqlite, safe_add_column, safe_drop_column

    bind = op.get_bind()

    # Note: ingredient_category show_* columns were permanently removed
    # and are not restored in downgrade as they no longer exist in models

    # Remove inventory item extensions (safe drop if exists)
    columns_to_drop = [
        'certifications',
        'fatty_acid_profile', 
        'brewing_diastatic_power_lintner',
        'brewing_potential_sg',
        'brewing_color_srm',
        'protein_content_pct',
        'inci_name',
        'recommended_fragrance_load_pct',
        'recommended_usage_rate'
    ]

    for column_name in columns_to_drop:
        safe_drop_column('inventory_item', column_name, verbose=False)

    # Drop new index prior to renaming column back
    try:
        op.execute("DROP INDEX IF EXISTS ix_global_item_aliases_gin")
    except Exception:
        pass

    # Revert column types before dropping (if columns still exist)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        columns = [col['name'] for col in inspector.get_columns('global_item')]

        # Revert global_item column types
        if 'recommended_usage_rate' in columns:
            with op.batch_alter_table('global_item') as batch_op:
                batch_op.alter_column('recommended_usage_rate',
                       existing_type=sa.String(length=64),
                       type_=sa.VARCHAR(length=128),
                       existing_nullable=True)

        if 'recommended_fragrance_load_pct' in columns:
            # Clean non-numeric data before conversion
            bind.execute(sa.text(r"""
                UPDATE global_item 
                SET recommended_fragrance_load_pct = NULL 
                WHERE recommended_fragrance_load_pct !~ '^[0-9]*\.?[0-9]+$'
                AND recommended_fragrance_load_pct IS NOT NULL
                AND recommended_fragrance_load_pct != ''
            """))

            with op.batch_alter_table('global_item') as batch_op:
                batch_op.alter_column('recommended_fragrance_load_pct',
                       existing_type=sa.String(length=64),
                       type_=sa.Float(),
                       existing_nullable=True,
                       postgresql_using='CASE WHEN recommended_fragrance_load_pct ~ \'^[0-9]*\\.?[0-9]+$\' THEN recommended_fragrance_load_pct::double precision ELSE NULL END')

        if 'is_active_ingredient' in columns:
            with op.batch_alter_table('global_item') as batch_op:
                batch_op.alter_column('is_active_ingredient',
                       existing_type=sa.BOOLEAN(),
                       nullable=True)

        # Revert inventory_item column types
        inv_columns = [col['name'] for col in inspector.get_columns('inventory_item')]

        if 'recommended_usage_rate' in inv_columns:
            with op.batch_alter_table('inventory_item') as batch_op:
                batch_op.alter_column('recommended_usage_rate',
                       existing_type=sa.String(length=64),
                       type_=sa.VARCHAR(length=128),
                       existing_nullable=True)

        if 'recommended_fragrance_load_pct' in inv_columns:
            # Clean non-numeric data before conversion
            bind.execute(sa.text(r"""
                UPDATE inventory_item 
                SET recommended_fragrance_load_pct = NULL 
                WHERE recommended_fragrance_load_pct !~ '^[0-9]*\.?[0-9]+$'
                AND recommended_fragrance_load_pct IS NOT NULL
                AND recommended_fragrance_load_pct != ''
            """))

            with op.batch_alter_table('inventory_item') as batch_op:
                batch_op.alter_column('recommended_fragrance_load_pct',
                       existing_type=sa.String(length=64),
                       type_=sa.Float(),
                       existing_nullable=True,
                       postgresql_using='CASE WHEN recommended_fragrance_load_pct ~ \'^[0-9]*\\.?[0-9]+$\' THEN recommended_fragrance_load_pct::double precision ELSE NULL END')

    except Exception as e:
        print(f"⚠️  Could not revert column types: {e}")

    # Remove global_item extensions (safe drop if exists)
    global_item_columns_to_drop = [
        'brewing_diastatic_power_lintner',
        'brewing_potential_sg', 
        'brewing_color_srm',
        'protein_content_pct',
        'fatty_acid_profile',
        'certifications',
        'inci_name',
        'recommended_fragrance_load_pct',
        'recommended_usage_rate',
        'is_active_ingredient'
    ]

    for column_name in global_item_columns_to_drop:
        safe_drop_column('global_item', column_name, verbose=False)

    # Rename column only if aliases exists (safe check)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        columns = [col['name'] for col in inspector.get_columns('global_item')]
        if 'aliases' in columns:
            with op.batch_alter_table('global_item') as batch_op:
                batch_op.alter_column('aliases', new_column_name='aka_names')
        elif 'aka_names' not in columns:
            # Neither column exists - this is unexpected but safe to skip
            print("⚠️  Neither 'aliases' nor 'aka_names' column found in global_item table")
    except Exception as e:
        print(f"⚠️  Could not rename aliases column: {e}")

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