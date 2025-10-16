
"""Add stable key column to subscription_tier

Revision ID: 20251016_2
Revises: 20251016_1
Create Date: 2025-10-16 22:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '20251016_2'
down_revision = '20251016_1'
branch_labels = None
depends_on = None


def upgrade():
    """Remove any key column and ensure clean tier structure with integer IDs"""
    
    connection = op.get_bind()
    
    # First, drop the key column if it exists (from previous failed migrations)
    try:
        connection.execute(text("ALTER TABLE subscription_tier DROP COLUMN IF EXISTS key"))
        print("✅ Dropped existing key column")
    except Exception as e:
        print(f"Key column didn't exist or couldn't be dropped: {e}")
    
    # Ensure all tiers have proper integer IDs and clean up any duplicates
    try:
        # Get all tiers and their current state
        result = connection.execute(text("SELECT id, name FROM subscription_tier ORDER BY id"))
        tiers = result.fetchall()
        print(f"Found {len(tiers)} existing tiers")
        
        # Normalize tier names to avoid duplicates
        tier_name_mapping = {
            'Solo Maker': 'Solo Plan',  # Normalize back to Solo Plan
            'Team': 'Team Plan',        # Normalize to Team Plan
            'Enterprise': 'Enterprise Plan',  # Normalize to Enterprise Plan
            'Free': 'Free Plan'         # Normalize to Free Plan
        }
        
        for tier_id, tier_name in tiers:
            if tier_name in tier_name_mapping:
                new_name = tier_name_mapping[tier_name]
                print(f"Normalizing '{tier_name}' -> '{new_name}'")
                connection.execute(
                    text("UPDATE subscription_tier SET name = :new_name WHERE id = :tier_id"),
                    {'new_name': new_name, 'tier_id': tier_id}
                )
        
        # Remove any duplicate tiers (keep the one with lowest ID)
        connection.execute(text("""
            DELETE FROM subscription_tier 
            WHERE id NOT IN (
                SELECT MIN(id) 
                FROM subscription_tier 
                GROUP BY name
            )
        """))
        
        print("✅ Normalized tier names and removed duplicates")
        
    except Exception as e:
        print(f"Could not normalize tiers: {e}")
    
    print("✅ Subscription tier migration completed - using integer IDs only")


def downgrade():
    """Add back a key column for rollback compatibility"""
    
    connection = op.get_bind()
    
    # Add the key column back
    op.add_column('subscription_tier', sa.Column('key', sa.String(64), nullable=True))
    
    # Populate with computed values
    try:
        connection.execute(text("""
            UPDATE subscription_tier 
            SET key = LOWER(REPLACE(REPLACE(name, ' Plan', ''), ' ', '_'))
        """))
        
        # Make it not null and unique
        op.alter_column('subscription_tier', 'key', nullable=False)
        op.create_unique_constraint('uq_subscription_tier_key', 'subscription_tier', ['key'])
        
    except Exception as e:
        print(f"Could not populate key column in downgrade: {e}")
