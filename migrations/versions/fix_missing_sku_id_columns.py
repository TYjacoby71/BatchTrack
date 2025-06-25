def upgrade():
    # Add sku_id column to product_inventory_history if it doesn't exist
    with op.batch_alter_table('product_inventory_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sku_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_product_inventory_history_sku_id', 'product_sku', ['sku_id'], ['id'])


def downgrade():
    # Remove sku_id column from product_inventory_history
    with op.batch_alter_table('product_inventory_history', schema=None) as batch_op:
        batch_op.drop_constraint('fk_product_inventory_history_sku_id', type_='foreignkey')
        batch_op.drop_column('sku_id')