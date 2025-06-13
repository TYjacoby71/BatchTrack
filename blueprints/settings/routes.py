from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, Unit, User
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
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
        settings_data=settings_data,
        inventory_units=Unit.query.all(),
        product_units=[]
    )

@settings_bp.route('/save', methods=['POST'])
@login_required
def save_settings():
    new_settings = request.get_json()
    
    try:
        # Load existing settings
        try:
            with open("settings.json", "r") as f:
                settings_data = json.load(f)
        except FileNotFoundError:
            settings_data = {}
        
        # Handle both full settings update and individual setting updates
        if len(new_settings) == 1 and not any(isinstance(v, dict) for v in new_settings.values()):
            # Individual setting update - map back to nested structure
            key, value = next(iter(new_settings.items()))
            
            # Map setting keys to their proper nested locations
            setting_mappings = {
                'max_dashboard_alerts': ('alerts', 'max_dashboard_alerts'),
                'show_expiration_alerts': ('alerts', 'show_expiration_alerts'),
                'show_timer_alerts': ('alerts', 'show_timer_alerts'),
                'show_low_stock_alerts': ('alerts', 'show_low_stock_alerts'),
                'show_batch_alerts': ('alerts', 'show_batch_alerts'),
                'show_fault_alerts': ('alerts', 'show_fault_alerts'),
                'low_stock_threshold': ('alerts', 'low_stock_threshold'),
                'expiration_warning_days': ('alerts', 'expiration_warning_days'),
                'show_inventory_refund': ('alerts', 'show_inventory_refund'),
                'show_alert_badges': ('alerts', 'show_alert_badges'),
                'require_timer_completion': ('batch_rules', 'require_timer_completion'),
                'allow_intermediate_tags': ('batch_rules', 'allow_intermediate_tags'),
                'require_finish_confirmation': ('batch_rules', 'require_finish_confirmation'),
                'stuck_batch_hours': ('batch_rules', 'stuck_batch_hours'),
                'enable_variations': ('recipe_builder', 'enable_variations'),
                'enable_containers': ('recipe_builder', 'enable_containers'),
                'auto_scale_recipes': ('recipe_builder', 'auto_scale_recipes'),
                'show_cost_breakdown': ('recipe_builder', 'show_cost_breakdown'),
                'enable_fifo_tracking': ('inventory', 'enable_fifo_tracking'),
                'show_expiration_dates': ('inventory', 'show_expiration_dates'),
                'auto_calculate_costs': ('inventory', 'auto_calculate_costs'),
                'enable_barcode_scanning': ('inventory', 'enable_barcode_scanning'),
                'show_supplier_info': ('inventory', 'show_supplier_info'),
                'enable_bulk_operations': ('inventory', 'enable_bulk_operations'),
                'enable_product_variants': ('products', 'enable_variants'),
                'show_profit_margins': ('products', 'show_profit_margins'),
                'auto_generate_skus': ('products', 'auto_generate_skus'),
                'enable_product_images': ('products', 'enable_product_images'),
                'track_production_costs': ('products', 'track_production_costs'),
                'items_per_page': ('display', 'per_page'),
                'enable_csv_export': ('display', 'enable_csv_export'),
                'auto_save_forms': ('display', 'auto_save_forms'),
                'dashboard_layout': ('display', 'dashboard_layout'),
                'show_quick_actions': ('display', 'show_quick_actions'),
                'compact_view': ('display', 'compact_view'),
                'reduce_animations': ('accessibility', 'reduce_animations'),
                'high_contrast_mode': ('accessibility', 'high_contrast_mode'),
                'keyboard_navigation': ('accessibility', 'keyboard_navigation'),
                'large_buttons': ('accessibility', 'large_buttons'),
                'auto_backup': ('system', 'auto_backup'),
                'log_level': ('system', 'log_level'),
                'browser_notifications': ('notifications', 'browser_notifications'),
                'email_alerts': ('notifications', 'email_alerts'),
                'alert_frequency': ('notifications', 'alert_frequency'),
                'quiet_hours_start': ('notifications', 'quiet_hours_start'),
                'quiet_hours_end': ('notifications', 'quiet_hours_end')
            }
            
            if key in setting_mappings:
                section, setting_key = setting_mappings[key]
                if section not in settings_data:
                    settings_data[section] = {}
                settings_data[section][setting_key] = value
        else:
            # Full settings update
            settings_data.update(new_settings)
        
        # Save updated settings
        with open("settings.json", "w") as f:
            json.dump(settings_data, f, indent=2)
        
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@settings_bp.route('/profile/save', methods=['POST'])
@login_required
def save_profile():
    try:
        data = request.get_json()
        
        # Update user profile fields
        if 'first_name' in data:
            current_user.first_name = data['first_name']
        if 'last_name' in data:
            current_user.last_name = data['last_name']
        if 'email' in data:
            current_user.email = data['email']
        if 'phone' in data:
            current_user.phone = data['phone']
            
        db.session.commit()
        return jsonify({"status": "success", "message": "Profile updated successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@settings_bp.route('/password/change', methods=['POST'])
@login_required
def change_password():
    try:
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        if not current_password or not new_password or not confirm_password:
            return jsonify({"status": "error", "message": "All fields are required"}), 400
            
        if not current_user.check_password(current_password):
            return jsonify({"status": "error", "message": "Current password is incorrect"}), 400
            
        if new_password != confirm_password:
            return jsonify({"status": "error", "message": "New passwords do not match"}), 400
            
        if len(new_password) < 6:
            return jsonify({"status": "error", "message": "Password must be at least 6 characters"}), 400
            
        current_user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        return jsonify({"status": "success", "message": "Password changed successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Catch-all route for unimplemented settings
@settings_bp.route('/<path:subpath>')
@login_required
def unimplemented_setting(subpath):
    flash('This setting is not yet implemented')
    return redirect(url_for('settings.index'))