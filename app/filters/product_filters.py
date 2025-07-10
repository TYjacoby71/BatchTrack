
import re
from flask import current_app

def register_product_filters(app):
    """Register product-related template filters"""
    
    @app.template_filter('parse_sale_data')
    def parse_sale_data(note):
        """Parse structured data from sale notes"""
        if not note:
            return {'quantity': None, 'sale_price': None, 'customer': None, 'notes': None}

        data = {'quantity': None, 'sale_price': None, 'customer': None, 'notes': None}

        # Parse FIFO deduction format: "FIFO deduction: 2.0 count of Base. Items used: 1. Reason: sale"
        fifo_match = re.search(r'FIFO deduction:\s*([\d.]+)\s*\w+', note)
        if fifo_match:
            data['quantity'] = fifo_match.group(1)

        # Parse sale format: "Sale: 1 × 4 oz Jar for $15.00 ($15.00/unit) to Customer Name"
        sale_match = re.search(r'Sale:\s*([\d.]+)\s*×.*?for\s*\$?([\d.]+)', note)
        if sale_match:
            data['quantity'] = sale_match.group(1)
            data['sale_price'] = f"${sale_match.group(2)}"

        # Parse customer
        customer_match = re.search(r'to\s+(.+?)(?:\.|$)', note)
        if customer_match:
            data['customer'] = customer_match.group(1).strip()

        # If no structured data found, put everything in notes
        if not any([data['quantity'], data['sale_price'], data['customer']]):
            data['notes'] = note

        return data

def product_variant_name(sku):
    """Get display name for product variant"""
    if not sku:
        return ""
    
    if hasattr(sku, 'variant') and sku.variant:
        return f"{sku.product.name} - {sku.variant.name}"
    elif hasattr(sku, 'variant_name') and sku.variant_name:
        return f"{sku.product_name} - {sku.variant_name}"
    else:
        return sku.product_name if hasattr(sku, 'product_name') else str(sku)

def ingredient_cost_currency(cost):
    """Format ingredient cost as currency"""
    if cost is None or cost == 0:
        return "$0.00"
    return f"${float(cost):.2f}"

def safe_float(value, default=0.0):
    """Safely convert value to float"""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def register_filters(app):
    """Register all template filters"""
    register_product_filters(app)
    
    @app.template_filter('get_fifo_summary')
    def get_fifo_summary_filter(inventory_id):
        """Template filter to get FIFO summary - removed as method no longer exists"""
        return None
