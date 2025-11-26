"""0011 community scout foundations

Revision ID: 0011_community_scout
Revises: 0010_recipe_status_drafts
Create Date: 2025-11-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0011_community_scout'
down_revision = '0010_recipe_status_drafts'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'community_scout_batch',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('generated_by_job_id', sa.String(length=64), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('claimed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('claimed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['claimed_by_user_id'], ['user.id']),
    )
    op.create_index(
        'ix_community_scout_batch_status',
        'community_scout_batch',
        ['status'],
    )
    op.create_index(
        'ix_community_scout_batch_claimed_user',
        'community_scout_batch',
        ['claimed_by_user_id'],
    )

    op.create_table(
        'community_scout_candidate',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), nullable=True),
        sa.Column('item_snapshot_json', sa.JSON(), nullable=False),
        sa.Column('classification', sa.String(length=32), nullable=False, server_default='unique'),
        sa.Column('match_scores', sa.JSON(), nullable=True),
        sa.Column('sensitivity_flags', sa.JSON(), nullable=True),
        sa.Column('state', sa.String(length=32), nullable=False, server_default='open'),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['batch_id'], ['community_scout_batch.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
        sa.ForeignKeyConstraint(['resolved_by'], ['user.id']),
    )
    op.create_index(
        'ix_community_scout_candidate_state',
        'community_scout_candidate',
        ['state'],
    )
    op.create_index(
        'ix_community_scout_candidate_batch',
        'community_scout_candidate',
        ['batch_id'],
    )
    op.create_index(
        'ix_community_scout_candidate_org_state',
        'community_scout_candidate',
        ['organization_id', 'state'],
    )
    op.create_index(
        'ix_community_scout_candidate_class_state',
        'community_scout_candidate',
        ['classification', 'state'],
    )

    op.create_table(
        'community_scout_job_state',
        sa.Column('job_name', sa.String(length=64), primary_key=True),
        sa.Column('last_inventory_id_processed', sa.Integer(), nullable=True),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('lock_owner', sa.String(length=64), nullable=True),
        sa.Column('lock_expires_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_table('community_scout_job_state')
    op.drop_index('ix_community_scout_candidate_class_state', table_name='community_scout_candidate')
    op.drop_index('ix_community_scout_candidate_org_state', table_name='community_scout_candidate')
    op.drop_index('ix_community_scout_candidate_batch', table_name='community_scout_candidate')
    op.drop_index('ix_community_scout_candidate_state', table_name='community_scout_candidate')
    op.drop_table('community_scout_candidate')
    op.drop_index('ix_community_scout_batch_claimed_user', table_name='community_scout_batch')
    op.drop_index('ix_community_scout_batch_status', table_name='community_scout_batch')
    op.drop_table('community_scout_batch')
