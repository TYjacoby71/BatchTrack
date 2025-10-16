
"""Add stable key column to subscription_tier

Revision ID: 20251016_01
Revises: 20251015_04
Create Date: 2025-10-16 22:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '20251016_01'
down_revision = '20251015_04'
branch_labels = None
depends_on = None


def upgrade():
    """Add stable key column and populate from existing data"""
    
    # Add the key column
    op.add_column('subscription_tier', sa.Column('key', sa.String(64), nullable=True))
    
    # Get database connection
    connection = op.get_bind()
    
    # Update existing tiers with computed keys
    tiers_to_update = [
        ('Solo Plan', 'solo'),
        ('Solo Maker', 'solo'),  # Normalize back to 'solo' 
        ('Team Plan', 'team'),
        ('Team', 'team'),
        ('Enterprise Plan', 'enterprise'),
        ('Enterprise', 'enterprise'),
        ('Free Plan', 'free'),
        ('Free', 'free'),
        ('Starter', 'starter'),
        ('Pro', 'pro'),
        ('Business', 'business'),
        ('Exempt', 'exempt')
    ]
    
    for name, key in tiers_to_update:
        try:
            connection.execute(
                text("UPDATE subscription_tier SET key = :key WHERE name = :name"),
                key=key, name=name
            )
        except Exception as e:
            print(f"Could not update tier {name} to key {key}: {e}")
    
    # For any remaining tiers without keys, compute from name
    try:
        result = connection.execute(text("SELECT id, name FROM subscription_tier WHERE key IS NULL"))
        for row in result:
            computed_key = row[1].lower().replace(' ', '_').replace('plan', '').strip('_')
            connection.execute(
                text("UPDATE subscription_tier SET key = :key WHERE id = :id"),
                key=computed_key, id=row[0]
            )
    except Exception as e:
        print(f"Could not update remaining tiers: {e}")
    
    # Make the column non-nullable and unique
    op.alter_column('subscription_tier', 'key', nullable=False)
    op.create_unique_constraint('uq_subscription_tier_key', 'subscription_tier', ['key'])
    
    print("✅ Added stable key column to subscription_tier")


def downgrade():
    """Remove the key column"""
    op.drop_constraint('uq_subscription_tier_key', 'subscription_tier', type_='unique')
    op.drop_column('subscription_tier', 'key')
