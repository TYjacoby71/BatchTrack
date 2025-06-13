from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models import db, Unit
import json

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/', endpoint='index')
@login_required
def index():
    # Define default settings structure
    default_settings = {
            "batch_display": {
                "visible_columns": ["status", "recipe", "start_date", "end_date", "tags", "cost"],
                "per_page": 20,
                "show_costs": True,
                "show_yield": True
            },
            "alerts": {
                "low_stock_threshold": 5,
                "notification_type": "dashboard",
                "max_dashboard_alerts": 3,
                "show_expiration_alerts": True,
                "show_timer_alerts": True,
                "show_low_stock_alerts": True,
                "show_batch_alerts": False,
                "show_fault_alerts": True,
                "expiration_warning_days": 7,
                "show_inventory_refund": False,
                "show_alert_badges": True
            },
            "batch_rules": {
                "require_timer_completion": True,
                "allow_intermediate_tags": False,
                "stuck_batch_hours": 24,
                "auto_archive_completed": False,
                "require_finish_confirmation": True
            },
            "recipe_builder": {
                "enable_variations": True,
                "enable_containers": True,
                "auto_scale_recipes": False,
                "show_cost_breakdown": True,
                "enable_recipe_notes": True
            },
            "inventory": {
                "enable_fifo_tracking": True,
                "show_expiration_dates": True,
                "auto_calculate_costs": True,
                "enable_barcode_scanning": False,
                "show_supplier_info": True,
                "enable_bulk_operations": True
            },
            "products": {
                "enable_variants": True,
                "show_profit_margins": True,
                "auto_generate_skus": False,
                "enable_product_images": True,
                "track_production_costs": True
            },
            "display": {
                "per_page": 20,
                "enable_csv_export": True,
                "auto_save_forms": False,
                "dashboard_layout": "standard",
                "show_quick_actions": True,
                "compact_view": False
            },
            "accessibility": {
                "reduce_animations": False,
                "high_contrast_mode": False,
                "keyboard_navigation": True,
                "screen_reader_support": True,
                "large_buttons": False
            },
            "system": {
                "enable_debug_mode": False,
                "log_level": "INFO",
                "auto_backup": True,
                "maintenance_mode": False,
                "api_rate_limiting": True
            },
            "notifications": {
                "email_alerts": False,
                "browser_notifications": True,
                "alert_frequency": "immediate",
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "08:00"
            }
        }
    
    try:
        with open("settings.json", "r") as f:
            settings_data = json.load(f)
            # Merge with defaults in case new settings were added
            for key, value in default_settings.items():
                if key not in settings_data:
                    settings_data[key] = value
                elif isinstance(value, dict) and isinstance(settings_data[key], dict):
                    for subkey, subvalue in value.items():
                        if subkey not in settings_data[key]:
                            settings_data[key][subkey] = subvalue
    except FileNotFoundError:
        settings_data = default_settings
        # Create settings.json if it doesn't exist
        with open("settings.json", "w") as f:
            json.dump(settings_data, f, indent=2)

    # Convert dictionary to nested object for template compatibility
    class SettingsObject:
        def __init__(self, data):
            for key, value in data.items():
                if isinstance(value, dict):
                    setattr(self, key, SettingsObject(value))
                else:
                    setattr(self, key, value)
    
    settings_obj = SettingsObject(settings_data)
    
    return render_template(
        'settings/index.html',
        settings=settings_obj,
        inventory_units=Unit.query.all(),
        product_units=[]
    )

@settings_bp.route('/save', methods=['POST'])
@login_required
def save_settings():
    settings_data = request.get_json()
    try:
        with open("settings.json", "w") as f:
            json.dump(settings_data, f, indent=2)
        flash('Settings saved successfully')
        return jsonify({"status": "success"})
    except Exception as e:
        flash('Error saving settings')
        return jsonify({"status": "error", "message": str(e)}), 500

# Catch-all route for unimplemented settings
@settings_bp.route('/<path:subpath>')
@login_required
def unimplemented_setting(subpath):
    flash('This setting is not yet implemented')
    return redirect(url_for('settings.index'))