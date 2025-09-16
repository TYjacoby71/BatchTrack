
"""add domain_event and freshness_snapshot tables

Revision ID: 20250912_01
Revises: 20250916203500
Create Date: 2025-09-12 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision = '20250912_01'
down_revision = '20250911_06'
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists"""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    """Add domain_event and freshness_snapshot tables"""
    
    print("=== Adding domain_event and freshness_snapshot tables ===")
    
    # Create domain_event table if it doesn't exist
    if not table_exists('domain_event'):
        print("   Creating domain_event table...")
        op.create_table('domain_event',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('event_type', sa.String(length=128), nullable=False),
            sa.Column('aggregate_id', sa.Integer(), nullable=False),
            sa.Column('aggregate_type', sa.String(length=64), nullable=False),
            sa.Column('event_data', sa.JSON(), nullable=True),
            sa.Column('organization_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Add indexes for performance
        op.create_index(op.f('ix_domain_event_aggregate_id'), 'domain_event', ['aggregate_id'], unique=False)
        op.create_index(op.f('ix_domain_event_aggregate_type'), 'domain_event', ['aggregate_type'], unique=False)
        op.create_index(op.f('ix_domain_event_created_at'), 'domain_event', ['created_at'], unique=False)
        op.create_index(op.f('ix_domain_event_event_type'), 'domain_event', ['event_type'], unique=False)
        op.create_index(op.f('ix_domain_event_organization_id'), 'domain_event', ['organization_id'], unique=False)
        
        print("   ✅ domain_event table created successfully")
    else:
        print("   ⚠️  domain_event table already exists")
    
    # Create freshness_snapshot table if it doesn't exist
    if not table_exists('freshness_snapshot'):
        print("   Creating freshness_snapshot table...")
        op.create_table('freshness_snapshot',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('organization_id', sa.Integer(), nullable=False),
            sa.Column('snapshot_date', sa.Date(), nullable=False),
            sa.Column('total_inventory_items', sa.Integer(), nullable=True),
            sa.Column('items_expiring_30_days', sa.Integer(), nullable=True),
            sa.Column('items_expiring_7_days', sa.Integer(), nullable=True),
            sa.Column('items_expired', sa.Integer(), nullable=True),
            sa.Column('total_lots', sa.Integer(), nullable=True),
            sa.Column('lots_expiring_30_days', sa.Integer(), nullable=True),
            sa.Column('lots_expiring_7_days', sa.Integer(), nullable=True),
            sa.Column('lots_expired', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Add indexes for performance
        op.create_index(op.f('ix_freshness_snapshot_organization_id'), 'freshness_snapshot', ['organization_id'], unique=False)
        op.create_index(op.f('ix_freshness_snapshot_snapshot_date'), 'freshness_snapshot', ['snapshot_date'], unique=False)
        
        # Add unique constraint for organization + date
        op.create_unique_constraint('uq_freshness_snapshot_org_date', 'freshness_snapshot', ['organization_id', 'snapshot_date'])
        
        print("   ✅ freshness_snapshot table created successfully")
    else:
        print("   ⚠️  freshness_snapshot table already exists")
    
    print("✅ Domain event and freshness snapshot tables migration completed")


def downgrade():
    """Remove domain_event and freshness_snapshot tables"""
    print("=== Removing domain_event and freshness_snapshot tables ===")
    
    # Drop freshness_snapshot table
    if table_exists('freshness_snapshot'):
        print("   Dropping freshness_snapshot table...")
        op.drop_table('freshness_snapshot')
        print("   ✅ freshness_snapshot table dropped")
    else:
        print("   ⚠️  freshness_snapshot table does not exist")
    
    # Drop domain_event table
    if table_exists('domain_event'):
        print("   Dropping domain_event table...")
        op.drop_table('domain_event')
        print("   ✅ domain_event table dropped")
    else:
        print("   ⚠️  domain_event table does not exist")
    
    print("✅ Domain event and freshness snapshot tables removal completed")
