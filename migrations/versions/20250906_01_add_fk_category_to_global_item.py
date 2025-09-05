from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250906_01_add_fk_category_to_global_item'
down_revision = '20250905_01_global_item_soft_delete_and_inventory_ownership'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('global_item') as batch_op:
        batch_op.add_column(sa.Column('ingredient_category_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_global_item_ingredient_category_id', ['ingredient_category_id'], unique=False)
        batch_op.create_foreign_key('fk_global_item_ingredient_category', 'ingredient_category', ['ingredient_category_id'], ['id'])


def downgrade():
    with op.batch_alter_table('global_item') as batch_op:
        batch_op.drop_constraint('fk_global_item_ingredient_category', type_='foreignkey')
        batch_op.drop_index('ix_global_item_ingredient_category_id')
        batch_op.drop_column('ingredient_category_id')
        # keep reference_category for backward compatibility
