
"""Add organization scoping to remaining models

Revision ID: add_organization_scoping
Revises: dc2034e4443f
Create Date: 2025-06-24 23:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_organization_scoping'
down_revision = 'dc2034e4443f'
branch_labels = None
depends_on = None


def upgrade():
    # Add organization_id to models that are missing it
    with op.batch_alter_table('recipe_ingredient', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_recipe_ingredient_organization_id', 'organization', ['organization_id'], ['id'])

    with op.batch_alter_table('batch_ingredient', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_batch_ingredient_organization_id', 'organization', ['organization_id'], ['id'])

    with op.batch_alter_table('batch_container', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_batch_container_organization_id', 'organization', ['organization_id'], ['id'])

    with op.batch_alter_table('custom_unit_mapping', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('created_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_custom_unit_mapping_organization_id', 'organization', ['organization_id'], ['id'])
        batch_op.create_foreign_key('fk_custom_unit_mapping_created_by', 'user', ['created_by'], ['id'])

    with op.batch_alter_table('conversion_log', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_conversion_log_organization_id', 'organization', ['organization_id'], ['id'])

    with op.batch_alter_table('batch_timer', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('created_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_batch_timer_organization_id', 'organization', ['organization_id'], ['id'])
        batch_op.create_foreign_key('fk_batch_timer_created_by', 'user', ['created_by'], ['id'])

    with op.batch_alter_table('extra_batch_ingredient', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_extra_batch_ingredient_organization_id', 'organization', ['organization_id'], ['id'])

    with op.batch_alter_table('extra_batch_container', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_extra_batch_container_organization_id', 'organization', ['organization_id'], ['id'])

    with op.batch_alter_table('batch_inventory_log', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_batch_inventory_log_organization_id', 'organization', ['organization_id'], ['id'])

    with op.batch_alter_table('tag', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('created_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_tag_organization_id', 'organization', ['organization_id'], ['id'])
        batch_op.create_foreign_key('fk_tag_created_by', 'user', ['created_by'], ['id'])

    # Update existing data to use the first organization (for existing data)
    # This assumes you have at least one organization and want to assign existing data to it
    op.execute("""
        UPDATE recipe_ingredient 
        SET organization_id = (SELECT id FROM organization LIMIT 1)
        WHERE organization_id IS NULL
    """)
    
    op.execute("""
        UPDATE batch_ingredient 
        SET organization_id = (SELECT id FROM organization LIMIT 1)
        WHERE organization_id IS NULL
    """)
    
    op.execute("""
        UPDATE batch_container 
        SET organization_id = (SELECT id FROM organization LIMIT 1)
        WHERE organization_id IS NULL
    """)
    
    op.execute("""
        UPDATE custom_unit_mapping 
        SET organization_id = (SELECT id FROM organization LIMIT 1)
        WHERE organization_id IS NULL
    """)
    
    op.execute("""
        UPDATE conversion_log 
        SET organization_id = (SELECT id FROM organization LIMIT 1)
        WHERE organization_id IS NULL
    """)
    
    op.execute("""
        UPDATE batch_timer 
        SET organization_id = (SELECT id FROM organization LIMIT 1)
        WHERE organization_id IS NULL
    """)
    
    op.execute("""
        UPDATE extra_batch_ingredient 
        SET organization_id = (SELECT id FROM organization LIMIT 1)
        WHERE organization_id IS NULL
    """)
    
    op.execute("""
        UPDATE extra_batch_container 
        SET organization_id = (SELECT id FROM organization LIMIT 1)
        WHERE organization_id IS NULL
    """)
    
    op.execute("""
        UPDATE batch_inventory_log 
        SET organization_id = (SELECT id FROM organization LIMIT 1)
        WHERE organization_id IS NULL
    """)
    
    op.execute("""
        UPDATE tag 
        SET organization_id = (SELECT id FROM organization LIMIT 1)
        WHERE organization_id IS NULL
    """)


def downgrade():
    # Remove the added columns
    with op.batch_alter_table('tag', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tag_created_by', type_='foreignkey')
        batch_op.drop_constraint('fk_tag_organization_id', type_='foreignkey')
        batch_op.drop_column('created_by')
        batch_op.drop_column('organization_id')

    with op.batch_alter_table('batch_inventory_log', schema=None) as batch_op:
        batch_op.drop_constraint('fk_batch_inventory_log_organization_id', type_='foreignkey')
        batch_op.drop_column('organization_id')

    with op.batch_alter_table('extra_batch_container', schema=None) as batch_op:
        batch_op.drop_constraint('fk_extra_batch_container_organization_id', type_='foreignkey')
        batch_op.drop_column('organization_id')

    with op.batch_alter_table('extra_batch_ingredient', schema=None) as batch_op:
        batch_op.drop_constraint('fk_extra_batch_ingredient_organization_id', type_='foreignkey')
        batch_op.drop_column('organization_id')

    with op.batch_alter_table('batch_timer', schema=None) as batch_op:
        batch_op.drop_constraint('fk_batch_timer_created_by', type_='foreignkey')
        batch_op.drop_constraint('fk_batch_timer_organization_id', type_='foreignkey')
        batch_op.drop_column('created_by')
        batch_op.drop_column('organization_id')

    with op.batch_alter_table('conversion_log', schema=None) as batch_op:
        batch_op.drop_constraint('fk_conversion_log_organization_id', type_='foreignkey')
        batch_op.drop_column('organization_id')

    with op.batch_alter_table('custom_unit_mapping', schema=None) as batch_op:
        batch_op.drop_constraint('fk_custom_unit_mapping_created_by', type_='foreignkey')
        batch_op.drop_constraint('fk_custom_unit_mapping_organization_id', type_='foreignkey')
        batch_op.drop_column('created_by')
        batch_op.drop_column('organization_id')

    with op.batch_alter_table('batch_container', schema=None) as batch_op:
        batch_op.drop_constraint('fk_batch_container_organization_id', type_='foreignkey')
        batch_op.drop_column('organization_id')

    with op.batch_alter_table('batch_ingredient', schema=None) as batch_op:
        batch_op.drop_constraint('fk_batch_ingredient_organization_id', type_='foreignkey')
        batch_op.drop_column('organization_id')

    with op.batch_alter_table('recipe_ingredient', schema=None) as batch_op:
        batch_op.drop_constraint('fk_recipe_ingredient_organization_id', type_='foreignkey')
        batch_op.drop_column('organization_id')
