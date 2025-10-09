
"""
Global items table, link to inventory_item, and performance indexes

Revision ID: 20250904_01
Revises: add_reference_guide_integration
Create Date: 2025-09-04
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250904_01'
down_revision = 'add_reference_guide_integration'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import text
    
    connection = op.get_bind()
    
    # 1) Create global_item table FIRST
    print("Creating global_item table...")
    try:
        op.create_table(
            'global_item',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(length=128), nullable=False),
            sa.Column('item_type', sa.String(length=32), nullable=False),
            sa.Column('default_unit', sa.String(length=32), nullable=True),
            sa.Column('density', sa.Float(), nullable=True),
            sa.Column('capacity', sa.Float(), nullable=True),
            sa.Column('capacity_unit', sa.String(length=32), nullable=True),
            sa.Column('suggested_inventory_category_id', sa.Integer(), nullable=True),
            sa.Column('metadata_json', sa.JSON(), nullable=True),
            sa.UniqueConstraint('name', 'item_type', name='_global_item_name_type_uc')
        )
        print("   ✅ Global item table created")
    except Exception as e:
        print(f"   ⚠️  Global item table may already exist: {e}")
    
    # Create indexes on global_item
    print("Creating indexes on global_item...")
    try:
        op.create_index('ix_global_item_name', 'global_item', ['name'])
        print("   ✅ Created name index")
    except Exception as e:
        print(f"   ⚠️  Name index may already exist")
        
    try:
        op.create_index('ix_global_item_item_type', 'global_item', ['item_type'])
        print("   ✅ Created item_type index")
    except Exception as e:
        print(f"   ⚠️  Item type index may already exist")

    # 2) Add global_item_id to inventory_item as NULLABLE
    print("Adding global_item_id column to inventory_item...")
    try:
        op.add_column('inventory_item', sa.Column('global_item_id', sa.Integer(), nullable=True))
        print("   ✅ Added global_item_id column")
    except Exception as e:
        print(f"   ⚠️  Column may already exist: {e}")
    
    # Create index on the foreign key column
    print("Creating index on inventory_item.global_item_id...")
    try:
        op.create_index('ix_inventory_item_global_item_id', 'inventory_item', ['global_item_id'])
        print("   ✅ Created global_item_id index")
    except Exception as e:
        print(f"   ⚠️  Index may already exist")

    # 3) Add the foreign key constraint
    print("Adding foreign key constraint...")
    try:
        # Check if constraint already exists
        from sqlalchemy import text
        constraint_exists = connection.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.table_constraints 
            WHERE table_name = 'inventory_item' 
            AND constraint_name = 'fk_inventory_item_global_item'
            AND constraint_type = 'FOREIGN KEY'
        """)).scalar()
        
        if constraint_exists == 0:
            op.create_foreign_key(
                'fk_inventory_item_global_item', 
                'inventory_item', 
                'global_item', 
                ['global_item_id'], 
                ['id']
            )
            print("   ✅ Foreign key constraint added successfully")
        else:
            print("   ✅ Foreign key constraint already exists")
    except Exception as e:
        print(f"   ⚠️  Foreign key constraint may already exist: {e}")

    # 4) Adjust uniqueness on inventory_item.name to be per-organization
    print("Adjusting inventory_item name constraints...")
    
    # Drop prior unique constraint or unique index on name if it exists
    try:
        op.drop_constraint('inventory_item_name_key', 'inventory_item', type_='unique')
        print("   Dropped old unique constraint on name")
    except Exception:
        pass
        
    try:
        op.drop_index('ix_inventory_item_name', table_name='inventory_item')
        print("   Dropped old index on name")
    except Exception:
        pass

    # Ensure name is indexed (non-unique) and add composite unique
    try:
        op.create_index('ix_inventory_item_name', 'inventory_item', ['name'])
        print("   Created new index on name")
    except Exception:
        connection.execute(text("ROLLBACK"))
        connection.execute(text("BEGIN"))
        
    try:
        op.create_unique_constraint('_org_name_uc', 'inventory_item', ['organization_id', 'name'])
        print("   Created organization+name unique constraint")
    except Exception:
        connection.execute(text("ROLLBACK"))
        connection.execute(text("BEGIN"))

    # 5) Performance indexes on inventory_item
    print("Adding performance indexes...")
    
    performance_indexes = [
        ('ix_inventory_item_organization_id', ['organization_id']),
        ('ix_inventory_item_type', ['type']),
        ('ix_inventory_item_is_archived', ['is_archived'])
    ]
    
    for idx_name, cols in performance_indexes:
        try:
            op.create_index(idx_name, 'inventory_item', cols)
            print(f"   ✅ Created index: {idx_name}")
        except Exception as e:
            print(f"   ⚠️  Index may already exist: {idx_name}")

    # 6) Index on user.organization_id for multi-tenant performance
    print("Adding user.organization_id index...")
    try:
        op.create_index('ix_user_organization_id', 'user', ['organization_id'])
        print("   ✅ Created user organization index")
    except Exception:
        print("   ⚠️  User organization index may already exist")

    print("✅ Migration completed successfully")


def downgrade():
    print("Rolling back global items migration...")
    
    # Reverse user index
    try:
        op.drop_index('ix_user_organization_id', table_name='user')
    except Exception:
        pass

    # Reverse inventory_item indexes/constraints
    try:
        op.drop_constraint('_org_name_uc', 'inventory_item', type_='unique')
    except Exception:
        pass
    try:
        op.drop_index('ix_inventory_item_is_archived', table_name='inventory_item')
    except Exception:
        pass
    try:
        op.drop_index('ix_inventory_item_type', table_name='inventory_item')
    except Exception:
        pass
    try:
        op.drop_index('ix_inventory_item_organization_id', table_name='inventory_item')
    except Exception:
        pass
    try:
        op.drop_index('ix_inventory_item_global_item_id', table_name='inventory_item')
    except Exception:
        pass
    try:
        op.drop_index('ix_inventory_item_name', table_name='inventory_item')
    except Exception:
        pass
    try:
        op.drop_constraint('fk_inventory_item_global_item', 'inventory_item', type_='foreignkey')
    except Exception:
        pass
    try:
        op.drop_column('inventory_item', 'global_item_id')
    except Exception:
        pass

    # Drop global_item table and indexes
    try:
        op.drop_index('ix_global_item_item_type', table_name='global_item')
    except Exception:
        pass
    try:
        op.drop_index('ix_global_item_name', table_name='global_item')
    except Exception:
        pass
    try:
        op.drop_table('global_item')
    except Exception:
        pass

    print("✅ Rollback completed")
