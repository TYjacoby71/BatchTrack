from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from . import settings_bp
from ...extensions import db
from ...utils.timezone_utils import TimezoneUtils
from ...models import db, Unit, User, InventoryItem, UserPreferences, Organization
from ...utils.permissions import has_permission, require_permission
from ...utils.json_store import read_json_file, write_json_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone

@settings_bp.route('/')
@settings_bp.route('')
@login_required
def index():
    """Settings dashboard with organized sections"""
    # Get or create user preferences
    user_prefs_obj = UserPreferences.get_for_user(current_user.id)

    # Convert to dictionary for JSON serialization - handle None for developers
    if user_prefs_obj:
        user_prefs = {
            'max_dashboard_alerts': user_prefs_obj.max_dashboard_alerts,
            'show_expiration_alerts': user_prefs_obj.show_expiration_alerts,
            'show_timer_alerts': user_prefs_obj.show_timer_alerts,
            'show_low_stock_alerts': user_prefs_obj.show_low_stock_alerts,
            'show_batch_alerts': user_prefs_obj.show_batch_alerts,
            'show_fault_alerts': user_prefs_obj.show_fault_alerts,
            'show_alert_badges': user_prefs_obj.show_alert_badges,
            'dashboard_layout': user_prefs_obj.dashboard_layout,
            'compact_view': user_prefs_obj.compact_view,
                'show_quick_actions': user_prefs_obj.show_quick_actions,
                'theme': (user_prefs_obj.theme or 'system')
        }
    else:
        # Default preferences for developers or users without preferences
        user_prefs = {
            'max_dashboard_alerts': 3,
            'show_expiration_alerts': True,
            'show_timer_alerts': True,
            'show_low_stock_alerts': True,
            'show_batch_alerts': True,
            'show_fault_alerts': True,
            'show_alert_badges': True,
            'dashboard_layout': 'standard',
            'compact_view': False,
            'show_quick_actions': True,
            'theme': 'system'
        }

    # Get organization info for org owners
    is_org_owner = current_user.organization and current_user.organization.owner and current_user.organization.owner.id == current_user.id

    # Get system settings from file or use defaults
    system_settings = read_json_file("settings.json", default={}) or {}

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
            'auto_create_bulk_sku_on_variant': False,
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

    # Get available timezones grouped by region
    # Pass current user's timezone to highlight it
    detected_tz = current_user.timezone if current_user.is_authenticated else None
    grouped_timezones = TimezoneUtils.get_grouped_timezones(detected_tz)

    from ...services.billing_service import BillingService
    pricing_data = BillingService.get_comprehensive_pricing_data()

    return render_template('settings/index.html',
                         user_prefs=user_prefs,
                         system_settings=system_settings,
                         grouped_timezones=grouped_timezones,
                         is_org_owner=is_org_owner,
                         organization=current_user.organization,
                         has_permission=has_permission,
                         TimezoneUtils=TimezoneUtils,
                         pricing_data=pricing_data)

@settings_bp.route('/api/user-preferences')
@login_required
def get_user_preferences():
    """Get user preferences for current user"""
    try:
        user_prefs = UserPreferences.get_for_user(current_user.id)

        if user_prefs:
            return jsonify({
                'max_dashboard_alerts': user_prefs.max_dashboard_alerts,
                'show_expiration_alerts': user_prefs.show_expiration_alerts,
                'show_timer_alerts': user_prefs.show_timer_alerts,
                'show_low_stock_alerts': user_prefs.show_low_stock_alerts,
                'show_batch_alerts': user_prefs.show_batch_alerts,
                'show_fault_alerts': user_prefs.show_fault_alerts,
                'show_alert_badges': user_prefs.show_alert_badges,
                'dashboard_layout': user_prefs.dashboard_layout,
                'compact_view': user_prefs.compact_view,
                'show_quick_actions': user_prefs.show_quick_actions,
                'theme': (user_prefs.theme or 'system')
            })
        else:
            # Return defaults for developers or users without preferences
            return jsonify({
                'max_dashboard_alerts': 3,
                'show_expiration_alerts': True,
                'show_timer_alerts': True,
                'show_low_stock_alerts': True,
                'show_batch_alerts': True,
                'show_fault_alerts': True,
                'show_alert_badges': True,
                'dashboard_layout': 'standard',
                'compact_view': False,
                'show_quick_actions': True,
                'theme': 'system'
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

        # If no preferences exist (like for developers), don't try to update
        if not user_prefs:
            return jsonify({'success': False, 'message': 'User preferences not available for this user type'})

        # Update fields that are provided
        for key, value in data.items():
            if hasattr(user_prefs, key):
                setattr(user_prefs, key, value)

        user_prefs.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        flash('All preferences saved successfully', 'success')
        return jsonify({'success': True, 'message': 'Preferences updated successfully'})
    except Exception as e:
        flash('Error saving preferences', 'error')
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/api/system-settings', methods=['POST'])
@login_required
@require_permission('settings.edit')
def update_system_settings():
    """Update system settings (requires permission)"""
    try:
        data = request.get_json()

        # Load existing settings
        settings_data = read_json_file("settings.json", default={}) or {}

        # Update the settings
        settings_data.update(data)

        # Save updated settings
        write_json_file("settings.json", settings_data)

        return jsonify({'success': True, 'message': 'System settings updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/profile/save', methods=['POST'])
@login_required
def save_profile():
    try:
        print(f"Profile save request from user: {current_user.id}")

        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
            first_name = data.get('first_name', '').strip()
            last_name = data.get('last_name', '').strip()
            email = data.get('email', '').strip()
            phone = data.get('phone', '').strip()
            timezone = data.get('timezone', current_user.timezone)
        else:
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            timezone = request.form.get('timezone', current_user.timezone)

        print(f"Parsed data - First: '{first_name}', Last: '{last_name}', Email: '{email}', Phone: '{phone}'")

        # Validate required fields
        if not first_name or not last_name or not email:
            error_msg = 'First name, last name, and email are required'
            if request.is_json:
                return jsonify({'success': False, 'error': error_msg}), 400
            flash(error_msg, 'error')
            return redirect(request.referrer or url_for('settings.index'))

        # Update user fields
        current_user.first_name = first_name
        current_user.last_name = last_name
        current_user.email = email
        current_user.phone = phone
        current_user.timezone = timezone

        # Commit changes
        print("Attempting to save to database...")
        db.session.commit()
        print("Database save successful")

        if request.is_json:
            return jsonify({'success': True, 'message': 'Profile updated successfully'})
        else:
            flash('Profile updated successfully!', 'success')
            # Determine redirect target
            redirect_url = request.referrer or url_for('settings.index')
            if current_user.user_type == 'developer':
                redirect_url = url_for('developer.dashboard')
            return redirect(redirect_url)

    except Exception as e:
        print(f"Error in profile save: {str(e)}")
        import traceback
        traceback.print_exc()

        db.session.rollback()
        error_msg = f'Error updating profile: {str(e)}'

        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 500
        else:
            flash(error_msg, 'error')
            # Safe fallback redirect
            if current_user.user_type == 'developer':
                return redirect(url_for('developer.dashboard'))
            else:
                return redirect(url_for('settings.index'))

@settings_bp.route('/password/change', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    try:
        data = request.get_json()
        current_password = data.get('current')
        new_password = data.get('new')
        confirm_password = data.get('confirm')

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

@settings_bp.route('/set-backup-password', methods=['POST'])
@login_required
def set_backup_password():
    """Set backup password for OAuth users"""
    try:
        # Only allow OAuth users who don't have a password yet
        if not current_user.oauth_provider:
            return jsonify({'error': 'This feature is only for OAuth users'}), 400

        if current_user.password_hash:
            return jsonify({'error': 'You already have a password set'}), 400

        data = request.get_json()
        password = data.get('password')
        confirm_password = data.get('confirm_password')

        if not password or not confirm_password:
            return jsonify({'error': 'Both password fields are required'}), 400

        if password != confirm_password:
            return jsonify({'error': 'Passwords do not match'}), 400

        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400

        # Set the password
        current_user.set_password(password)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Backup password set successfully'})

    except Exception as e:
        db.session.rollback()
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
            ingredient = db.session.get(InventoryItem, ingredient_data['id'])
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
            container = db.session.get(InventoryItem, container_data['id'])
            if container and container.type == 'container':
                container.name = container_data['name']
                # Canonical keys only
                if 'capacity' in container_data:
                    container.capacity = container_data.get('capacity')
                if 'capacity_unit' in container_data:
                    container.capacity_unit = container_data.get('capacity_unit')
                container.cost_per_unit = container_data['cost_per_unit']
                updated_count += 1

        db.session.commit()
        return jsonify({'success': True, 'updated_count': updated_count})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@settings_bp.route('/update-timezone', methods=['POST'])
@login_required
def update_timezone():
    timezone = request.form.get('timezone')

    if timezone and TimezoneUtils.validate_timezone(timezone):
        current_user.timezone = timezone
        db.session.commit()
        flash('Timezone updated successfully', 'success')
    else:
        flash(f'Invalid timezone selected. Please choose from the available options.', 'error')
    return redirect(url_for('settings.index'))

@settings_bp.route('/update-user-preference', methods=['POST'])
@login_required
def update_user_preference():
    """Update user preference via AJAX"""
    try:
        data = request.get_json()
        key = data.get('key')
        value = data.get('value')

        if not key:
            flash('Preference key is required', 'error')
            return jsonify({'error': 'Preference key is required'}), 400

        # Get or create user preferences
        user_prefs = UserPreferences.get_for_user(current_user.id)

        # Update the preference
        if hasattr(user_prefs, key):
            setattr(user_prefs, key, value)
            db.session.commit()
            flash('Preference saved successfully', 'success')
            return jsonify({'success': True})
        else:
            flash('Invalid preference key', 'error')
            return jsonify({'error': 'Invalid preference key'}), 400

    except Exception as e:
        db.session.rollback()
        flash('Error saving preference', 'error')
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/update-system-setting', methods=['POST'])
@login_required
def update_system_setting():
    """Update system setting via AJAX"""
    try:
        data = request.get_json()
        section = data.get('section')
        key = data.get('key')
        value = data.get('value')

        if not all([section, key]):
            flash('Section and key are required', 'error')
            return jsonify({'error': 'Section and key are required'}), 400

        settings_data = read_json_file("settings.json", default={}) or {}
        section_settings = settings_data.get(section)
        if not isinstance(section_settings, dict):
            section_settings = {}
            settings_data[section] = section_settings

        section_settings[key] = value
        write_json_file("settings.json", settings_data)

        flash('System setting saved successfully', 'success')
        return jsonify({'success': True})

    except Exception as e:
        flash('Error saving system setting', 'error')
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/user-management')
@login_required
def user_management():
    """User management page for profile and account settings"""
    # Get all users separated by type
    customer_users = User.query.filter(User.user_type != 'developer').all()
    developer_users = User.query.filter(User.user_type == 'developer').all()

    return render_template('settings/user_management.html',
                         customer_users=customer_users,
                         developer_users=developer_users)

# System settings moved to admin section

# All organization-related routes have been moved to the organization blueprint
# Settings blueprint now focuses only on user preferences and system settings
