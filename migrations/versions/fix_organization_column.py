
"""fix_organization_id_column

Revision ID: fix_organization_column
Revises: 2b44df52e87b
Create Date: 2025-06-13 20:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_organization_column'
down_revision = '2b44df52e87b'
branch_labels = None
depends_on = None


def upgrade():
    # Check if organization_id column exists, if not add it
    connection = op.get_bind()
    
    # Check if column exists
    try:
        result = connection.execute(sa.text("PRAGMA table_info(user)")).fetchall()
        columns = [row[1] for row in result]
        
        if 'organization_id' not in columns:
            # Add the column
            with op.batch_alter_table('user', schema=None) as batch_op:
                batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
            
            # Create personal organizations for existing users
            users = connection.execute(sa.text("SELECT id, username FROM user")).fetchall()
            
            for user in users:
                # Create personal organization for each user
                connection.execute(sa.text(
                    "INSERT INTO organization (name, subscription_tier, is_active) VALUES (:name, 'free', 1)"
                ), {"name": f"{user.username}'s Organization"})
                
                # Get the organization ID
                org_id = connection.execute(sa.text("SELECT last_insert_rowid()")).scalar()
                
                # Update user with organization_id
                connection.execute(sa.text(
                    "UPDATE user SET organization_id = :org_id WHERE id = :user_id"
                ), {"org_id": org_id, "user_id": user.id})
            
            # Make organization_id NOT NULL after backfilling
            with op.batch_alter_table('user', schema=None) as batch_op:
                batch_op.alter_column('organization_id', nullable=False)
                batch_op.create_foreign_key('fk_user_organization_id', 'organization', ['organization_id'], ['id'])
    except Exception as e:
        print(f"Migration error: {e}")
        raise


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_constraint('fk_user_organization_id', type_='foreignkey')
        batch_op.drop_column('organization_id')
