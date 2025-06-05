
"""Ensure every product has a Base ProductVariation

Revision ID: ensure_base_variants
Revises: 068534518f6c
Create Date: 2025-06-04 18:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'ensure_base_variants'
down_revision = '068534518f6c'
branch_labels = None
depends_on = None

def upgrade():
    # Create a session to work with
    bind = op.get_bind()
    session = Session(bind=bind)
    
    # Find all products that don't have a "Base" variation
    result = session.execute(text("""
        SELECT p.id, p.name, p.created_at
        FROM product p
        WHERE p.id NOT IN (
            SELECT DISTINCT pv.product_id 
            FROM product_variation pv 
            WHERE pv.name = 'Base'
        )
    """))
    
    products_without_base = result.fetchall()
    
    # Create Base variations for products that don't have them
    for product_id, product_name, created_at in products_without_base:
        session.execute(text("""
            INSERT INTO product_variation (product_id, name, description, created_at)
            VALUES (:product_id, 'Base', 'Default base variant', :created_at)
        """), {
            'product_id': product_id,
            'created_at': created_at
        })
    
    # Update any inventory with variant='Base' but ensure it references the Base ProductVariation
    # This is for consistency, even though inventory will continue to use variant field as string
    
    session.commit()

def downgrade():
    # Remove Base variations that were auto-created
    bind = op.get_bind()
    session = Session(bind=bind)
    
    session.execute(text("""
        DELETE FROM product_variation 
        WHERE name = 'Base' AND description = 'Default base variant'
    """))
    
    session.commit()
