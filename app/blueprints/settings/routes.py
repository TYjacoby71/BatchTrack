from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from . import settings_bp
from ...extensions import db
from ...utils.timezone_utils import TimezoneUtils
from ...models import db, Unit, User, InventoryItem, UserPreferences, Organization
from ...utils.permissions import has_permission, require_permission
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

from . import settings_bp

@settings_bp.route('/')
@login_required
def index():
    """Settings dashboard with organized sections"""
    # Get or create user preferences
    user_prefs_obj = UserPreferences.get_for_user(current_user.id)

    # Convert to dictionary for JSON serialization
    user_prefs = {
        'max_dashboard_alerts': user_prefs_obj.max_dashboard_alerts,
        'show_expiration_alerts': user_prefs_obj.show_expiration_alerts,
        'show_timer_alerts': user_prefs_obj.show_timer_alerts,
        'show_timer_alerts': user_prefs_obj.show_timer_alerts,
        'show_low_stock_alerts': user_prefs_obj.show_low_stock_alerts,
        'show_batch_alerts': user_prefs_obj.show_batch_alerts,
        'show_fault_alerts': user_prefs_obj.show_fault_alerts,
        'expiration_warning_days': user_prefs_obj.expiration_warning_days,
        'show_alert_badges': user_prefs_obj.show_alert_badges,
        'dashboard_layout': user_prefs_obj.dashboard_layout,
        'compact_view': user_prefs_obj.compact_view,
        'show_quick_actions': user_prefs_obj.show_quick_actions
    }

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

    available_timezones = TimezoneUtils.get_available_timezones()
    return render_template('settings/index.html', 
                         user_prefs=user_prefs,
                         system_settings=system_settings,
                         is_org_owner=is_org_owner,
                         available_timezones=available_timezones)

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

@settings_bp.route('/update-timezone', methods=['POST'])
@login_required
def update_timezone():
    timezone = request.form.get('timezone')
    if timezone and timezone in TimezoneUtils.get_available_timezones():
        current_user.timezone = timezone
        db.session.commit()
        flash('Timezone updated successfully', 'success')
    else:
        flash('Invalid timezone selected', 'error')
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
            return jsonify({'error': 'Preference key is required'}), 400

        # Get or create user preferences
        user_prefs = UserPreferences.get_for_user(current_user.id)

        # Update the preference
        if hasattr(user_prefs, key):
            setattr(user_prefs, key, value)
            db.session.commit()
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Invalid preference key'}), 400

    except Exception as e:
        db.session.rollback()
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
            return jsonify({'error': 'Section and key are required'}), 400

        # For now, just return success - implement actual system settings storage later
        # This could be stored in a SystemSettings model or configuration file
        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/organization/dashboard')
@login_required
def organization_dashboard():
    """Organization dashboard for managing users, roles, and settings (organization owners only)"""

    # Check if user is organization owner only - developers should not access this
    if not (current_user.user_type == 'organization_owner' or current_user.is_organization_owner):
        abort(403)

    # Get organization data
    organization = current_user.organization
    if not organization:
        flash('No organization found', 'error')
        return redirect(url_for('settings.index'))

    # Get users for this organization (developers have organization_id=None so are automatically excluded)
    users = User.query.filter_by(organization_id=current_user.organization_id).all()

    # Get organization-appropriate roles (exclude developer role)
    from ...models.role import Role
    roles = Role.query.filter(Role.name != 'developer').all()
    for role in roles:
        # Add assigned users count to each role
        role.assigned_users = User.query.filter_by(role_id=role.id, organization_id=organization.id).all()

    # Get permissions grouped by category
    from ...models.permission import Permission
    permissions = Permission.query.all()
    permission_categories = {}
    for perm in permissions:
        category = perm.category or 'general'
        if category not in permission_categories:
            permission_categories[category] = []
        permission_categories[category].append(perm)

    return render_template('settings/org_dashboard.html',
                         organization=organization,
                         users=users,
                         roles=roles,
                         permissions=permissions,
                         permission_categories=permission_categories)

@settings_bp.route('/organization/invite-user', methods=['POST'])
@login_required
@require_permission('organization.manage')
def invite_user():
    """Invite a new user to the organization"""
    try:
        data = request.get_json()

        # Validate required fields
        email = data.get('email')
        role_id = data.get('role_id')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')

        if not email or not role_id:
            return jsonify({'success': False, 'error': 'Email and role are required'})

        # Check if user already exists
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'error': 'User with this email already exists'})

        # Check if organization can add more users
        if not current_user.organization.can_add_users():
            return jsonify({'success': False, 'error': 'Organization has reached user limit for current subscription'})

        # For now, create user directly (later we'll implement proper invites)
        # Generate a temporary username from email
        username = email.split('@')[0]
        counter = 1
        original_username = username
        while User.query.filter_by(username=username).first():
            username = f"{original_username}{counter}"
            counter += 1

        # Create new user with temporary password
        import secrets
        temp_password = secrets.token_urlsafe(12)

        new_user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role_id=role_id,
            organization_id=current_user.organization_id,
            is_active=True,
            user_type='team_member'
        )
        new_user.set_password(temp_password)

        db.session.add(new_user)
        db.session.commit()

        # In a real implementation, send email with login details
        # For now, we'll just return success

        return jsonify({
            'success': True, 
            'message': f'User invited successfully. Username: {username}, Temp password: {temp_password}'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@settings_bp.route('/organization/update', methods=['POST'])
@login_required
@require_permission('organization.manage')
def update_organization():
    """Update organization settings"""
    try:
        data = request.get_json()
        organization = current_user.organization

        # Update organization fields
        if 'name' in data:
            organization.name = data['name']

        # Add other organization settings here as needed

        db.session.commit()

        return jsonify({'success': True, 'message': 'Organization settings updated'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@settings_bp.route('/organization/export/<report_type>')
@login_required
@require_permission('organization.manage')
def export_report(report_type):
    """Export various organization reports"""
    try:
        if report_type == 'users':
            # Export users CSV
            users = User.query.filter_by(organization_id=current_user.organization_id).all()
            # Implement CSV export logic
            flash('User export functionality coming soon', 'info')
        elif report_type == 'batches':
            # Export batch history
            flash('Batch export functionality coming soon', 'info')
        elif report_type == 'inventory':
            # Export inventory movements
            flash('Inventory export functionality coming soon', 'info')
        elif report_type == 'activity':
            # Export activity log
            flash('Activity export functionality coming soon', 'info')
        else:
            flash('Unknown report type', 'error')

        return redirect(url_for('settings.organization_dashboard'))

    except Exception as e:
        flash(f'Export error: {str(e)}', 'error')
        return redirect(url_for('settings.organization_dashboard'))

@settings_bp.route('/organization/add-user', methods=['POST'])
@login_required
@require_permission('organization.manage')
def add_user():
    """Add a new user to the organization (org owners only) - legacy endpoint"""
    try:
        data = request.get_json()

        # Validate required fields
        username = data.get('username')
        email = data.get('email') 
        password = data.get('password')
        role_id = data.get('role_id')

        if not all([username, email, password, role_id]):
            return jsonify({'success': False, 'error': 'All fields are required'})

        # Check if user already exists
        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'error': 'Username already exists'})

        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'error': 'Email already exists'})

        # Check if organization can add more users
        if not current_user.organization.can_add_users():
            return jsonify({'success': False, 'error': 'Organization has reached user limit for current subscription'})

        # Create new user
        new_user = User(
            username=username,
            email=email,
            role_id=role_id,
            organization_id=current_user.organization_id,
            is_active=True,
            user_type='team_member'
        )
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        return jsonify({'success': True, 'message': 'User added successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})