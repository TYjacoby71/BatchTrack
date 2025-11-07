"""Expand global and inventory item attributes and simplify ingredient categories.

Revision ID: 0006_global_item_extended_attributes
Revises: 0005_cleanup_guardrails_0005_cleanup_guardrails
Create Date: 2025-11-07
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0006_global_item_extended_attributes'
down_revision = '0005_cleanup_guardrails_0005_cleanup_guardrails'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    with op.batch_alter_table('global_item') as batch_op:
        batch_op.alter_column('aka_names', new_column_name='aliases')
        batch_op.add_column(sa.Column('recommended_usage_rate', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('recommended_fragrance_load_pct', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('inci_name', sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column('certifications', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('fatty_acid_profile', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('protein_content_pct', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('brewing_color_srm', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('brewing_potential_sg', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('brewing_diastatic_power_lintner', sa.Float(), nullable=True))

    if dialect == 'postgresql':
        op.execute("DROP INDEX IF EXISTS ix_global_item_aka_gin")
        op.execute("CREATE INDEX IF NOT EXISTS ix_global_item_aliases_gin ON global_item USING gin ((aliases::jsonb))")
    else:
        op.execute("DROP INDEX IF EXISTS ix_global_item_aka_gin")

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


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    with op.batch_alter_table('ingredient_category') as batch_op:
        batch_op.add_column(sa.Column('show_comedogenic_rating', sa.Boolean(), nullable=True, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('show_shelf_life_days', sa.Boolean(), nullable=True, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('show_moisture_content', sa.Boolean(), nullable=True, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('show_ph_value', sa.Boolean(), nullable=True, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('show_flash_point', sa.Boolean(), nullable=True, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('show_melting_point', sa.Boolean(), nullable=True, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('show_iodine_value', sa.Boolean(), nullable=True, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('show_saponification_value', sa.Boolean(), nullable=True, server_default=sa.text('0')))

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

    if dialect == 'postgresql':
        op.execute("DROP INDEX IF EXISTS ix_global_item_aliases_gin")
        op.execute("CREATE INDEX IF NOT EXISTS ix_global_item_aka_gin ON global_item USING gin ((aka_names::jsonb))")

