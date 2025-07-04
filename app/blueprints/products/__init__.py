
from flask import Blueprint

# Import all blueprints
from .products import products_bp
from .sku import sku_bp
from .product_variants import product_variants_bp
from .product_inventory_routes import product_inventory_bp
from .api import products_api_bp

# Create alias for backward compatibility
api_bp = products_api_bp
