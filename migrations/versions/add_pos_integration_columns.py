def upgrade():
    # Add POS integration fields to inventory_history table
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('order_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('reservation_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('is_reserved', sa.Boolean(), nullable=True, default=False))

    # Add frozen_quantity field to inventory_item table
    with op.batch_alter_table('inventory_item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('frozen_quantity', sa.Float(), nullable=True, default=0.0))
        batch_op.add_column(sa.Column('available_quantity', sa.Float(), nullable=True, default=0.0))


def downgrade():
    # Remove POS integration fields from inventory_history
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        batch_op.drop_column('is_reserved')
        batch_op.drop_column('reservation_id')
        batch_op.drop_column('order_id')

    # Remove frozen_quantity field from inventory_item
    with op.batch_alter_table('inventory_item', schema=None) as batch_op:
        batch_op.drop_column('available_quantity')
        batch_op.drop_column('frozen_quantity')