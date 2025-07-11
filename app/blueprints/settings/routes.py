from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from ...models import db, Unit, User, InventoryItem
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

from . import settings_bp
# Replacement of settings routes and addition of user preferences model and endpoints.
@settings_bp.route('/')
@login_required
def index():
    """Settings dashboard"""
    # Get current settings from file or use defaults
    try:
        with open("settings.json", "r") as f:
            settings = json.load(f)
    except FileNotFoundError:
        settings = {}

    # Ensure all required sections exist with defaults
    defaults = {
        'alerts': {
            'max_dashboard_alerts': 10,
            'show_expiration_alerts': True,
            'show_timer_alerts': True,
            'show_low_stock_alerts': True,
            'show_batch_alerts': True,
            'show_fault_alerts': True,
            'low_stock_threshold': 5,
            'expiration_warning_days': 7,
            'show_inventory_refund': True,
            'show_alert_badges': True
        },
        'display': {
            'dashboard_layout': 'standard',
            'compact_view': False,
            'show_quick_actions': True
        }
    }
    
    # Merge defaults with existing settings
    for section, section_settings in defaults.items():
        if section not in settings:
            settings[section] = section_settings
        else:
            for key, value in section_settings.items():
                if key not in settings[section]:
                    settings[section][key] = value

    return render_template('settings/index.html', settings=settings)

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

@settings_bp.route('/bulk-update-ingredients', methods=['POST'])
@login_required
def bulk_update_ingredients():
    try:
        data = request.get_json()
        ingredients = data.get('ingredients', [])

        updated_count = 0
        for ingredient_data in ingredients:
            ingredient = InventoryItem.query.get(ingredient_data['id'])
            if ingredient:
                ingredient.name = ingredient_data['name']
                ingredient.unit = ingredient_data['unit']
                ingredient.cost_per_unit = ingredient_data['cost_per_unit']
                updated_count += 1

        db.session.commit()
        return jsonify({'success': True, 'updated_count': updated_count})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@settings_bp.route('/bulk-update-containers', methods=['POST'])
@login_required
def bulk_update_containers():
    try:
        data = request.get_json()
        containers = data.get('containers', [])

        updated_count = 0
        for container_data in containers:
            container = InventoryItem.query.get(container_data['id'])
            if container and container.type == 'container':
                container.name = container_data['name']
                container.storage_amount = container_data['storage_amount']
                container.storage_unit = container_data['storage_unit']
                container.cost_per_unit = container_data['cost_per_unit']
                updated_count += 1

        db.session.commit()
        return jsonify({'success': True, 'updated_count': updated_count})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# Catch-all route for unimplemented settings
@settings_bp.route('/<path:subpath>')
@login_required
def unimplemented_setting(subpath):
    flash('This setting is not yet implemented')
    return redirect(url_for('settings.index'))
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app
from flask_login import login_required, current_user
from ...utils.permissions import require_permission
from ...utils.settings import SettingsManager
from ...models import db, UserPreferences
import json

from . import settings_bp

@settings_bp.route('/api/update', methods=['POST'])
@login_required
def update_setting():
    """Update a specific setting"""
    try:
        data = request.get_json()
        setting_key = data.get('key')
        setting_value = data.get('value')
        category = data.get('category', 'general')

        if not setting_key:
            return jsonify({'error': 'Setting key is required'}), 400

        success = SettingsManager.update_setting(category, setting_key, setting_value)

        if success:
            return jsonify({'success': True, 'message': 'Setting updated successfully'})
        else:
            return jsonify({'error': 'Failed to update setting'}), 500

    except Exception as e:
        current_app.logger.error(f"Error updating setting: {str(e)}")
        return jsonify({'error': str(e)}), 500



