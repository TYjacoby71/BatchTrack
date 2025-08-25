"""clean subscription tier billing structure

Revision ID: clean_subscription_tier_billing
Revises: 57d6ce45a761
Create Date: 2025-08-14 23:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'clean_subscription_tier_billing'
down_revision = '57d6ce45a761'
branch_labels = None
depends_on = None

def upgrade():
    """Ensure billing_provider defaults and constraints are correct"""
    connection = op.get_bind()

    # Update any NULL billing_provider values to 'exempt'
    connection.execute(
        sa.text("UPDATE subscription_tier SET billing_provider = 'exempt' WHERE billing_provider IS NULL")
    )

    print("✅ Billing provider cleanup completed")

def downgrade():
    """Nothing to downgrade"""
    pass