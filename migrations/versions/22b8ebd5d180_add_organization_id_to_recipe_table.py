"""add_organization_id_to_recipe_table

Revision ID: 22b8ebd5d180
Revises: 4693135414dc
Create Date: 2025-06-13 20:57:50.678703

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '22b8ebd5d180'
down_revision = '4693135414dc'
branch_labels = None
depends_on = None


def upgrade():
    # Add organization_id column to recipe table
    with op.batch_alter_table('recipe', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))

    # Set default organization_id for existing recipes (get from recipe creator's organization)
    connection = op.get_bind()
    
    # Update recipes with organization_id based on their creator's organization
    connection.execute(sa.text("""
        UPDATE recipe 
        SET organization_id = (
            SELECT user.organization_id 
            FROM user 
            WHERE user.id = recipe.created_by
        ) 
        WHERE recipe.created_by IS NOT NULL
    """))
    
    # For recipes without a creator, assign to the first organization
    connection.execute(sa.text("""
        UPDATE recipe 
        SET organization_id = (SELECT MIN(id) FROM organization) 
        WHERE organization_id IS NULL
    """))

    # Make the column non-nullable after setting defaults
    with op.batch_alter_table('recipe', schema=None) as batch_op:
        batch_op.alter_column('organization_id', nullable=False)
        batch_op.create_foreign_key('fk_recipe_organization_id', 'organization', ['organization_id'], ['id'])


def downgrade():
    # Remove foreign key constraint
    with op.batch_alter_table('recipe', schema=None) as batch_op:
        batch_op.drop_constraint('fk_recipe_organization_id', type_='foreignkey')
        batch_op.drop_column('organization_id')
