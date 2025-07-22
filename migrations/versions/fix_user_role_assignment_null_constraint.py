
"""fix user_role_assignment null constraint

Revision ID: fix_user_role_assignment_null_constraint
Revises: consolidate_all_heads_final
Create Date: 2025-07-22 04:47:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_user_role_assignment_null_constraint'
down_revision = 'bd55298f5ebc'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the existing table and recreate with proper constraints
    # First, save existing data
    connection = op.get_bind()
    
    # Get existing data
    existing_data = connection.execute(sa.text("SELECT * FROM user_role_assignment")).fetchall()
    
    # Drop and recreate table with proper constraints
    op.drop_table('user_role_assignment')
    
    op.create_table('user_role_assignment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=True),  # Allow NULL
        sa.Column('developer_role_id', sa.Integer(), nullable=True),  # Allow NULL
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.Column('assigned_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['assigned_by'], ['user.id'], ),
        sa.ForeignKeyConstraint(['developer_role_id'], ['developer_role.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
        sa.ForeignKeyConstraint(['role_id'], ['role.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add constraint that either role_id OR developer_role_id must be set (but not both)
    with op.batch_alter_table('user_role_assignment', schema=None) as batch_op:
        batch_op.create_check_constraint(
            'ck_user_role_assignment_role_xor',
            '(role_id IS NOT NULL AND developer_role_id IS NULL) OR (role_id IS NULL AND developer_role_id IS NOT NULL)'
        )
    
    # Restore existing data
    if existing_data:
        for row in existing_data:
            connection.execute(sa.text("""
                INSERT INTO user_role_assignment 
                (id, user_id, role_id, developer_role_id, organization_id, is_active, assigned_at, assigned_by)
                VALUES (:id, :user_id, :role_id, :developer_role_id, :organization_id, :is_active, :assigned_at, :assigned_by)
            """), {
                'id': row[0],
                'user_id': row[1], 
                'role_id': row[2],
                'developer_role_id': row[3],
                'organization_id': row[4],
                'is_active': row[5],
                'assigned_at': row[6],
                'assigned_by': row[7]
            })


def downgrade():
    # Remove the check constraint using batch mode
    with op.batch_alter_table('user_role_assignment', schema=None) as batch_op:
        batch_op.drop_constraint('ck_user_role_assignment_role_xor', type_='check')
    
    # Recreate table with old constraints (role_id NOT NULL)
    connection = op.get_bind()
    existing_data = connection.execute(sa.text("SELECT * FROM user_role_assignment")).fetchall()
    
    op.drop_table('user_role_assignment')
    
    op.create_table('user_role_assignment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),  # NOT NULL
        sa.Column('developer_role_id', sa.Integer(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.Column('assigned_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['assigned_by'], ['user.id'], ),
        sa.ForeignKeyConstraint(['developer_role_id'], ['developer_role.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
        sa.ForeignKeyConstraint(['role_id'], ['role.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Restore data (filtering out any rows with NULL role_id)
    if existing_data:
        for row in existing_data:
            if row[2] is not None:  # Only restore rows with non-NULL role_id
                connection.execute(sa.text("""
                    INSERT INTO user_role_assignment 
                    (id, user_id, role_id, developer_role_id, organization_id, is_active, assigned_at, assigned_by)
                    VALUES (:id, :user_id, :role_id, :developer_role_id, :organization_id, :is_active, :assigned_at, :assigned_by)
                """), {
                    'id': row[0],
                    'user_id': row[1], 
                    'role_id': row[2],
                    'developer_role_id': row[3],
                    'organization_id': row[4],
                    'is_active': row[5],
                    'assigned_at': row[6],
                    'assigned_by': row[7]
                })
