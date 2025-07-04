from flask import Blueprint

# Import all blueprints
from .products import products_bp
from .sku import sku_bp
from .api import api_bp
from .product_variants import product_variants_bp
from .product_inventory_routes import product_inventory_bp