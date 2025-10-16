"""
Create feature_flag table
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20251015_02'
down_revision = '20251015_01'
branch_labels = None
depends_on = None

def table_exists(table_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()

def upgrade():
    if not table_exists('feature_flag'):
        op.create_table(
            'feature_flag',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('key', sa.String(length=128), nullable=False, unique=True, index=True),
            sa.Column('description', sa.String(length=255), nullable=True),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )
        try:
            op.create_index('ix_feature_flag_key', 'feature_flag', ['key'], unique=True)
        except Exception:
            pass


def downgrade():
    try:
        op.drop_index('ix_feature_flag_key', table_name='feature_flag')
    except Exception:
        pass
    op.drop_table('feature_flag')
