from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250906_01'
down_revision = '20250905_01'
branch_labels = None
depends_on = None


def upgrade():
    # Check if column already exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('global_item')]

    if 'ingredient_category_id' not in columns:
        with op.batch_alter_table('global_item') as batch_op:
            batch_op.add_column(sa.Column('ingredient_category_id', sa.Integer(), nullable=True))
            batch_op.create_index(batch_op.f('ix_global_item_ingredient_category_id'), ['ingredient_category_id'], unique=False)
            batch_op.create_foreign_key('fk_global_item_ingredient_category_id', 'ingredient_category', ['ingredient_category_id'], ['id'])
    else:
        print("Column ingredient_category_id already exists on global_item, skipping...")


def downgrade():
    # Check if column exists before trying to drop it
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('global_item')]

    if 'ingredient_category_id' in columns:
        with op.batch_alter_table('global_item') as batch_op:
            batch_op.drop_constraint('fk_global_item_ingredient_category_id', type_='foreignkey')
            batch_op.drop_index(batch_op.f('ix_global_item_ingredient_category_id'))
            batch_op.drop_column('ingredient_category_id')
    else:
        print("Column ingredient_category_id does not exist on global_item, skipping...")