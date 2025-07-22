
"""create_developer_tables

Revision ID: create_developer_tables
Revises: consolidate_all_heads_final
Create Date: 2025-07-22 04:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'create_developer_tables'
down_revision = 'consolidate_all_heads_final'
branch_labels = None
depends_on = None


def upgrade():
    # Create developer_permission table
    op.create_table('developer_permission',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=32), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # Create developer_role table
    op.create_table('developer_role',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=32), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # Create association table for developer roles and permissions
    op.create_table('developer_role_permission',
        sa.Column('developer_role_id', sa.Integer(), nullable=False),
        sa.Column('developer_permission_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['developer_permission_id'], ['developer_permission.id'], ),
        sa.ForeignKeyConstraint(['developer_role_id'], ['developer_role.id'], ),
        sa.PrimaryKeyConstraint('developer_role_id', 'developer_permission_id')
    )


def downgrade():
    op.drop_table('developer_role_permission')
    op.drop_table('developer_role')
    op.drop_table('developer_permission')
