from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from ...models import db, Unit, User, InventoryItem, UserPreferences, Organization
from ...utils.permissions import has_permission, require_permission
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

from . import settings_bp
from ...models.user_preferences import UserPreferences
from ...utils.settings import SystemSettings

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

@settings_bp.route('/api/settings', methods=['GET'])
@login_required
def get_settings():
    """Get current user settings"""
    try:
        user_prefs = UserPreferences.get_for_user(current_user.id)
        system_settings = SystemSettings.get_all()

        # Build settings response
        settings = {
            'alerts': {
                'max_dashboard_alerts': user_prefs.max_dashboard_alerts if user_prefs else 10,
                'low_stock_threshold': user_prefs.low_stock_threshold if user_prefs else 5,
                'expiration_warning_days': user_prefs.expiration_warning_days if user_prefs else 7,
                'show_expiration_alerts': user_prefs.show_expiration_alerts if user_prefs else True,
                'show_timer_alerts': user_prefs.show_timer_alerts if user_prefs else True,
                'show_low_stock_alerts': user_prefs.show_low_stock_alerts if user_prefs else True,
                'show_batch_alerts': user_prefs.show_batch_alerts if user_prefs else True,
                'show_fault_alerts': user_prefs.show_fault_alerts if user_prefs else True,
                'show_alert_badges': user_prefs.show_alert_badges if user_prefs else True,
            },
            'batch_rules': {
                'require_timer_completion': system_settings.get('require_timer_completion', True),
                'allow_intermediate_tags': system_settings.get('allow_intermediate_tags', False),
                'require_finish_confirmation': system_settings.get('require_finish_confirmation', True),
                'stuck_batch_hours': system_settings.get('stuck_batch_hours', 24),
            },
            'recipe_builder': {
                'enable_variations': system_settings.get('enable_variations', True),
                'enable_containers': system_settings.get('enable_containers', True),
                'auto_scale_recipes': system_settings.get('auto_scale_recipes', False),
                'show_cost_breakdown': system_settings.get('show_cost_breakdown', True),
            }
        }

        return jsonify(settings)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/api/settings', methods=['POST'])
@login_required
def save_settings():
    """Save user settings"""
    try:
        data = request.get_json()

        # Update user preferences
        user_prefs = UserPreferences.get_for_user(current_user.id)
        if not user_prefs:
            user_prefs = UserPreferences(user_id=current_user.id)

        if 'alerts' in data:
            alerts = data['alerts']
            user_prefs.max_dashboard_alerts = alerts.get('max_dashboard_alerts', 10)
            user_prefs.low_stock_threshold = alerts.get('low_stock_threshold', 5)
            user_prefs.expiration_warning_days = alerts.get('expiration_warning_days', 7)
            user_prefs.show_expiration_alerts = alerts.get('show_expiration_alerts', True)
            user_prefs.show_timer_alerts = alerts.get('show_timer_alerts', True)
            user_prefs.show_low_stock_alerts = alerts.get('show_low_stock_alerts', True)
            user_prefs.show_batch_alerts = alerts.get('show_batch_alerts', True)
            user_prefs.show_fault_alerts = alerts.get('show_fault_alerts', True)
            user_prefs.show_alert_badges = alerts.get('show_alert_badges', True)

        db.session.add(user_prefs)

        # Update system settings
        if 'batch_rules' in data:
            batch_rules = data['batch_rules']
            SystemSettings.set('require_timer_completion', batch_rules.get('require_timer_completion', True))
            SystemSettings.set('allow_intermediate_tags', batch_rules.get('allow_intermediate_tags', False))
            SystemSettings.set('require_finish_confirmation', batch_rules.get('require_finish_confirmation', True))
            SystemSettings.set('stuck_batch_hours', batch_rules.get('stuck_batch_hours', 24))

        if 'recipe_builder' in data:
            recipe_builder = data['recipe_builder']
            SystemSettings.set('enable_variations', recipe_builder.get('enable_variations', True))
            SystemSettings.set('enable_containers', recipe_builder.get('enable_containers', True))
            SystemSettings.set('auto_scale_recipes', recipe_builder.get('auto_scale_recipes', False))
            SystemSettings.set('show_cost_breakdown', recipe_builder.get('show_cost_breakdown', True))

        db.session.commit()
        return jsonify({'success': True, 'message': 'Settings saved successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/')
@login_required
def index():
    """Settings dashboard with organized sections"""
    # Get or create user preferences
    user_prefs = UserPreferences.get_for_user(current_user.id)

    # Get organization info for org owners
    is_org_owner = current_user.organization and current_user.organization.owner and current_user.organization.owner.id == current_user.id

    # Get system settings from file or use defaults
    try:
        with open("settings.json", "r") as f:
            system_settings = json.load(f)
    except FileNotFoundError:
        system_settings = {}

    # Ensure all required sections exist with defaults
    system_defaults = {
        'batch_rules': {
            'require_timer_completion': False,
            'allow_intermediate_tags': True,
            'require_finish_confirmation': True,
            'stuck_batch_hours': 24
        },
        'recipe_builder': {
            'enable_variations': True,
            'enable_containers': True,
            'auto_scale_recipes': False,
            'show_cost_breakdown': True
        },
        'inventory': {
            'enable_fifo_tracking': True,
            'show_expiration_dates': True,
            'auto_calculate_costs': True,
            'enable_barcode_scanning': False,
            'show_supplier_info': True,
            'enable_bulk_operations': True
        },
        'products': {
            'enable_variants': True,
            'show_profit_margins': True,
            'auto_generate_skus': False,
            'enable_product_images': True,
            'track_production_costs': True
        },
        'system': {
            'auto_backup': False,
            'log_level': 'INFO',
            'per_page': 25,
            'enable_csv_export': True,
            'auto_save_forms': False
        },
        'notifications': {
            'browser_notifications': True,
            'email_alerts': False,
            'alert_frequency': 'real_time',
            'quiet_hours_start': '22:00',
            'quiet_hours_end': '08:00'
        }
    }

    # Merge defaults with existing settings
    for section, section_settings in system_defaults.items():
        if section not in system_settings:
            system_settings[section] = section_settings
        else:
            for key, value in section_settings.items():
                if key not in system_settings[section]:
                    system_settings[section][key] = value

    return render_template('settings/index.html', 
                         user_prefs=user_prefs,
                         system_settings=system_settings,
                         is_org_owner=is_org_owner)

@settings_bp.route('/api/user-preferences')
@login_required
def get_user_preferences():
    """Get user preferences for current user"""
    try:
        user_prefs = UserPreferences.get_for_user(current_user.id)
        return jsonify({
            'max_dashboard_alerts': user_prefs.max_dashboard_alerts,
            'show_expiration_alerts': user_prefs.show_expiration_alerts,
            'show_timer_alerts': user_prefs.show_timer_alerts,
            'show_low_stock_alerts': user_prefs.show_low_stock_alerts,
            'show_batch_alerts': user_prefs.show_batch_alerts,
            'show_fault_alerts': user_prefs.show_fault_alerts,
            'expiration_warning_days': user_prefs.expiration_warning_days,
            'show_alert_badges': user_prefs.show_alert_badges,
            'dashboard_layout': user_prefs.dashboard_layout,
            'compact_view': user_prefs.compact_view,
            'show_quick_actions': user_prefs.show_quick_actions
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/api/user-preferences', methods=['POST'])
@login_required
def update_user_preferences():
    """Update user preferences"""
    try:
        data = request.get_json()
        user_prefs = UserPreferences.get_for_user(current_user.id)

        # Update fields that are provided
        for key, value in data.items():
            if hasattr(user_prefs, key):
                setattr(user_prefs, key, value)

        user_prefs.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({'success': True, 'message': 'Preferences updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/api/system-settings', methods=['POST'])
@login_required
@require_permission('settings.edit')
def update_system_settings():
    """Update system settings (requires permission)"""
    try:
        data = request.get_json()

        # Load existing settings
        try:
            with open("settings.json", "r") as f:
                settings_data = json.load(f)
        except FileNotFoundError:
            settings_data = {}

        # Update the settings
        settings_data.update(data)

        # Save updated settings
        with open("settings.json", "w") as f:
            json.dump(settings_data, f, indent=2)

        return jsonify({'success': True, 'message': 'System settings updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/organization')
@login_required
@require_permission('organization.manage')
def organization_management():
    """Organization management page (org owners only)"""
    if not current_user.organization:
        flash('No organization found', 'error')
        return redirect(url_for('settings.index'))

    organization = current_user.organization
    users = User.query.filter_by(organization_id=organization.id).all()

    return render_template('settings/organization.html', 
                         organization=organization,
                         users=users)

@settings_bp.route('/organization/add-user', methods=['POST'])
@login_required
@require_permission('organization.manage')
def add_user_to_organization():
    """Add a new user to the organization"""
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        role_id = data.get('role_id')

        if not all([username, email, password]):
            return jsonify({'error': 'All fields are required'}), 400

        # Check if user already exists
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already exists'}), 400

        # Create new user
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            organization_id=current_user.organization_id,
            role_id=role_id,
            is_active=True
        )

        db.session.add(new_user)
        db.session.commit()

        return jsonify({'success': True, 'message': 'User added successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/profile/save', methods=['POST'])
@login_required
def save_profile():
    """Save user profile information"""
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
        return jsonify({'success': True, 'message': 'Profile updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/password/change', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    try:
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')

        if not current_password or not new_password or not confirm_password:
            return jsonify({'error': 'All fields are required'}), 400

        if not current_user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 400

        if new_password != confirm_password:
            return jsonify({'error': 'New passwords do not match'}), 400

        if len(new_password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400

        current_user.password_hash = generate_password_hash(new_password)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Password changed successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/bulk-update-ingredients', methods=['POST'])
@login_required
@require_permission('inventory.edit')
def bulk_update_ingredients():
    """Bulk update ingredients"""
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
@require_permission('inventory.edit')
def bulk_update_containers():
    """Bulk update containers"""
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