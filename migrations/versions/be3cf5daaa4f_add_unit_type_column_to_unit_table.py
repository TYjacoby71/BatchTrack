
"""add unit_type column to unit table

Revision ID: be3cf5daaa4f
Revises: fix_nullable_constraints
Create Date: 2025-08-01 20:05:51.807718

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'be3cf5daaa4f'
down_revision = 'fix_nullable_constraints'
branch_labels = None
depends_on = None


def upgrade():
    print("=== Fixing unit_type column and cleaning up ===")
    
    bind = op.get_bind()
    
    # First, update any NULL unit_type values to a default value
    print("Updating NULL unit_type values...")
    bind.execute(text('UPDATE unit SET unit_type = :default WHERE unit_type IS NULL'), {"default": "volume"})
    
    # Drop the temporary table if it exists
    try:
        op.drop_table('_alembic_tmp_organization')
        print("Dropped temporary organization table")
    except Exception as e:
        print(f"Could not drop temp table (may not exist): {e}")
    
    # Clean up organization table
    with op.batch_alter_table('organization', schema=None) as batch_op:
        try:
            batch_op.drop_column('updated_at')
            print("Dropped organization.updated_at column")
        except Exception as e:
            print(f"Could not drop organization.updated_at: {e}")

    # Clean up role table
    with op.batch_alter_table('role', schema=None) as batch_op:
        try:
            batch_op.drop_column('updated_at')
            print("Dropped role.updated_at column")
        except Exception as e:
            print(f"Could not drop role.updated_at: {e}")

    # Now fix the unit table - make unit_type NOT NULL and drop the old type column
    with op.batch_alter_table('unit', schema=None) as batch_op:
        # Make unit_type NOT NULL (values are now populated)
        batch_op.alter_column('unit_type',
               existing_type=sa.VARCHAR(length=32),
               nullable=False)
        print("Made unit_type column NOT NULL")
        
        # Drop the old type column if it exists
        try:
            batch_op.drop_column('type')
            print("Dropped old unit.type column")
        except Exception as e:
            print(f"Could not drop unit.type column (may not exist): {e}")

    # Clean up user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        try:
            batch_op.drop_column('updated_at')
            print("Dropped user.updated_at column")
        except Exception as e:
            print(f"Could not drop user.updated_at: {e}")

    print("✅ Migration completed successfully")


def downgrade():
    print("=== Reverting unit_type column changes ===")
    
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('updated_at', sa.DATETIME(), nullable=True))

    with op.batch_alter_table('unit', schema=None) as batch_op:
        batch_op.add_column(sa.Column('type', sa.VARCHAR(length=32), nullable=False))
        batch_op.alter_column('unit_type',
               existing_type=sa.VARCHAR(length=32),
               nullable=True)

    with op.batch_alter_table('role', schema=None) as batch_op:
        batch_op.add_column(sa.Column('updated_at', sa.DATETIME(), nullable=True))

    with op.batch_alter_table('organization', schema=None) as batch_op:
        batch_op.add_column(sa.Column('updated_at', sa.DATETIME(), nullable=True))

    op.create_table('_alembic_tmp_organization',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('name', sa.VARCHAR(length=128), nullable=False),
    sa.Column('contact_email', sa.VARCHAR(length=256), nullable=True),
    sa.Column('created_at', sa.DATETIME(), nullable=True),
    sa.Column('is_active', sa.BOOLEAN(), nullable=True),
    sa.Column('signup_source', sa.VARCHAR(length=64), nullable=True),
    sa.Column('promo_code', sa.VARCHAR(length=32), nullable=True),
    sa.Column('referral_code', sa.VARCHAR(length=32), nullable=True),
    sa.Column('subscription_tier_id', sa.INTEGER(), nullable=True),
    sa.Column('subscription_tier', sa.VARCHAR(length=32), nullable=True),
    sa.ForeignKeyConstraint(['subscription_tier_id'], ['subscription_tier.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    
    print("✅ Downgrade completed")
