
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models import db, InventoryUnit, ProductUnit
import json

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/', endpoint='settings')
@login_required
def settings():
    try:
        with open("settings.json", "r") as f:
            settings_data = json.load(f)
    except:
        settings_data = {
            "batch_display": {
                "visible_columns": ["status", "recipe", "start_date", "end_date"],
                "default_filters": {"status": "all"}
            },
            "alerts": {
                "low_stock_threshold": 5,
                "notification_type": "dashboard"
            },
            "inventory": {
                "show_ingredients": True,
                "show_containers": True
            },
            "product_defaults": {
                "default_unit": "pieces",
                "enable_fifo": True
            },
            "batch_rules": {
                "require_timer_completion": True,
                "allow_intermediate_tags": False
            },
            "printing": {
                "default_layout": "recipe_card",
                "show_costs": False
            },
            "qr_settings": {
                "auto_generate": True,
                "base_url": ""
            },
            "recipe_builder": {
                "enable_variations": True,
                "enable_containers": True
            }
        }
    
    return render_template(
        'settings/index.html',
        settings=settings_data,
        inventory_units=InventoryUnit.query.all(),
        product_units=ProductUnit.query.all()
    )

@settings_bp.route('/save', methods=['POST'])
@login_required
def save_settings():
    settings_data = request.get_json()
    with open("settings.json", "w") as f:
        json.dump(settings_data, f, indent=2)
    flash('Settings saved successfully')
    return jsonify({"status": "success"})
