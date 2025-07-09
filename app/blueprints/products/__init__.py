from flask import Blueprint

products_bp = Blueprint('products', __name__, url_prefix='/products')

from . import products, product_variants, sku, api, product_inventory_routes, reservation_routes