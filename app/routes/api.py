
from flask import Blueprint, jsonify
from app.routes.utils import load_data

api_bp = Blueprint("api", __name__)

FEATURE_FLAGS = {
    "enable_product_api": True  # Set to False to disable external API access
}

@api_bp.route('/api/products', methods=['GET'])
def api_get_products():
    if not FEATURE_FLAGS.get("enable_product_api"):
        return jsonify({"error": "Product API access is currently disabled."}), 403

    data = load_data()
    products = data.get("products", [])
    enriched_products = []

    for p in products:
        enriched_products.append({
            "product": p.get("product"),
            "yield": p.get("yield"),
            "unit": p.get("unit"),
            "notes": p.get("notes", ""),
            "label_info": p.get("label_info", ""),
            "timestamp": p.get("timestamp"),
            "price_per_unit": p.get("price_per_unit", ""),
            "sku": p.get("sku", ""),
            "synced_to_shopify": p.get("synced_to_shopify", False)
        })

    return jsonify(enriched_products)
