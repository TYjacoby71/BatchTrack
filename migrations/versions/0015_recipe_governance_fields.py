"""0015 recipe governance fields

Revision ID: 0015_recipe_governance_fields
Revises: 0014_batchbot_stack
Create Date: 2025-11-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0015_recipe_governance_fields'
down_revision = '0014_batchbot_stack'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'organization',
        sa.Column(
            'recipe_sales_blocked',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        'organization',
        sa.Column(
            'recipe_library_blocked',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        'organization',
        sa.Column(
            'recipe_violation_count',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )
    op.add_column(
        'organization',
        sa.Column(
            'recipe_policy_notes',
            sa.Text(),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column('organization', 'recipe_policy_notes')
    op.drop_column('organization', 'recipe_violation_count')
    op.drop_column('organization', 'recipe_library_blocked')
    op.drop_column('organization', 'recipe_sales_blocked')
