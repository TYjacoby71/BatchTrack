from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Organization, User, Permission, Role
from app.extensions import db
from datetime import datetime, timedelta
from sqlalchemy import func
from .system_roles import system_roles_bp
from .subscription_tiers import subscription_tiers_bp

developer_bp = Blueprint('developer', __name__, url_prefix='/developer')
developer_bp.register_blueprint(system_roles_bp)
developer_bp.register_blueprint(subscription_tiers_bp)

@developer_bp.before_request
def require_developer():
    """Ensure only developers can access these routes"""
    if not current_user.is_authenticated:
        flash('Developer access required', 'error')
        return redirect(url_for('auth.login'))

    # Check if user is a developer
    if current_user.user_type != 'developer':
        flash('Developer access required', 'error')
        return redirect(url_for('auth.login'))

@developer_bp.route('/dashboard')
@login_required
def dashboard():
    """Main developer system dashboard"""
    # System statistics
    total_orgs = Organization.query.count()
    active_orgs = Organization.query.filter_by(is_active=True).count()
    total_users = User.query.filter(User.user_type != 'developer').count()
    active_users = User.query.filter(
        User.user_type != 'developer',
        User.is_active == True
    ).count()

    # Subscription tier breakdown - get from organization's subscription tiers
    from app.models.subscription_tier import SubscriptionTier
    subscription_stats = db.session.query(
        SubscriptionTier.key,
        func.count(Organization.id).label('count')
    ).join(Organization, Organization.subscription_tier_id == SubscriptionTier.id).group_by(SubscriptionTier.key).all()

    # Recent organizations (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_orgs = Organization.query.filter(
        Organization.created_at >= thirty_days_ago
    ).order_by(Organization.created_at.desc()).limit(10).all()

    # Organizations needing attention (no active users, overdue payments, etc.)
    problem_orgs = Organization.query.filter(
        Organization.is_active == True
    ).all()

    # Filter for orgs with no active users
    problem_orgs = [org for org in problem_orgs if org.active_users_count == 0]

    return render_template('developer/dashboard.html',
                         total_orgs=total_orgs,
                         active_orgs=active_orgs,
                         total_users=total_users,
                         active_users=active_users,
                         subscription_stats=subscription_stats,
                         recent_orgs=recent_orgs,
                         problem_orgs=problem_orgs)

@developer_bp.route('/organizations')
@login_required
def organizations():
    """Organization management and customer support filtering"""
    organizations = Organization.query.all()
    selected_org_id = session.get('dev_selected_org_id')
    selected_org = None

    if selected_org_id:
        selected_org = Organization.query.get(selected_org_id)

    return render_template('developer/organizations.html', 
                         organizations=organizations,
                         selected_org=selected_org)

@developer_bp.route('/organizations/create', methods=['GET', 'POST'])
@login_required
def create_organization():
    """Create new organization with owner user"""
    # Load available tiers for the form
    from .subscription_tiers import load_tiers_config
    tiers_config = load_tiers_config()

    # Include all tiers for developer creation (including internal ones)
    available_tiers = {
        key: tier for key, tier in tiers_config.items() 
        if isinstance(tier, dict) and tier.get('is_available', True)
    }

    if request.method == 'POST':
        # Organization details
        name = request.form.get('name')
        subscription_tier = request.form.get('subscription_tier', 'free')
        creation_reason = request.form.get('creation_reason')
        notes = request.form.get('notes', '')

        # User details
        username = request.form.get('username')
        email = request.form.get('email')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')
        phone = request.form.get('phone')

        # Validation
        if not name:
            flash('Organization name is required', 'error')
            return redirect(url_for('developer.create_organization'))

        if not username:
            flash('Username is required', 'error')
            return redirect(url_for('developer.create_organization'))

        if not email:
            flash('Email is required', 'error')
            return redirect(url_for('developer.create_organization'))

        if not password:
            flash('Password is required', 'error')
            return redirect(url_for('developer.create_organization'))

        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists', 'error')
            return redirect(url_for('developer.create_organization'))

        try:
            # Create organization
            org = Organization(
                name=name,
                contact_email=email,
                is_active=True
            )
            db.session.add(org)
            db.session.flush()  # Get the ID

            # Assign subscription tier to organization
            from app.models.subscription_tier import SubscriptionTier
            tier_record = SubscriptionTier.query.filter_by(key=subscription_tier).first()
            if tier_record:
                org.subscription_tier_id = tier_record.id
            else:
                # Default to exempt tier if tier not found
                exempt_tier = SubscriptionTier.query.filter_by(key='exempt').first()
                if exempt_tier:
                    org.subscription_tier_id = exempt_tier.id

            # Create organization owner user
            owner_user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                organization_id=org.id,
                user_type='customer',
                is_organization_owner=True,
                is_active=True
            )
            owner_user.set_password(password)
            db.session.add(owner_user)
            db.session.flush()  # Get the user ID

            # Assign organization owner role
            from app.models.role import Role
            org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
            if org_owner_role:
                owner_user.assign_role(org_owner_role)

            db.session.commit()

            flash(f'Organization "{name}" and owner user "{username}" created successfully', 'success')
            return redirect(url_for('developer.organization_detail', org_id=org.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating organization: {str(e)}', 'error')
            return redirect(url_for('developer.create_organization'))

    return render_template('developer/create_organization.html', available_tiers=available_tiers)

@developer_bp.route('/organizations/<int:org_id>')
@login_required
def organization_detail(org_id):
    """Detailed organization management"""
    org = Organization.query.get_or_404(org_id)
    users_query = User.query.filter_by(organization_id=org_id).all()

    # Convert User objects to dictionaries for JSON serialization
    users = []
    for user in users_query:
        user_dict = {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'phone': user.phone,
            'user_type': user.user_type,
            'is_organization_owner': user.is_organization_owner,
            'is_active': user.is_active,
            'created_at': user.created_at.strftime('%Y-%m-%d') if user.created_at else None,
            'last_login': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else None,
            'full_name': user.full_name
        }
        users.append(user_dict)

    # Load subscription tiers config for the dropdown
    from .subscription_tiers import load_tiers_config
    all_tiers_config = load_tiers_config()

    # Filter to only include dictionary objects (valid tier configurations)
    tiers_config = {}
    for tier_key, tier_data in all_tiers_config.items():
        if isinstance(tier_data, dict) and tier_data.get('is_available', True):
            tiers_config[tier_key] = tier_data

    # Debug subscription info
    current_tier = org.effective_subscription_tier
    tier_record = org.tier

    print(f"DEBUG: Organization {org.name} (ID: {org.id})")
    print(f"DEBUG: Has tier record: {tier_record is not None}")
    if tier_record:
        print(f"DEBUG: Tier key: {tier_record.key}")
        print(f"DEBUG: Tier name: {tier_record.name}")
    print(f"DEBUG: Effective tier: {current_tier}")
    print(f"DEBUG: Available tiers: {list(tiers_config.keys())}")

    return render_template('developer/organization_detail.html',
                         organization=org,
                         users=users,
                         users_objects=users_query,  # Pass original objects for template iteration
                         tiers_config=tiers_config,
                         current_tier=current_tier)

@developer_bp.route('/organizations/<int:org_id>/edit', methods=['POST'])
@login_required
def edit_organization(org_id):
    """Edit organization details"""
    org = Organization.query.get_or_404(org_id)

    # Debug form data
    print(f"DEBUG: Form data received: {dict(request.form)}")

    old_name = org.name
    old_active = org.is_active
    old_tier = org.effective_subscription_tier

    org.name = request.form.get('name', org.name)
    org.is_active = request.form.get('is_active') == 'true'

    # Update subscription tier if provided
    new_tier = request.form.get('subscription_tier')
    print(f"DEBUG: Updating tier from '{old_tier}' to '{new_tier}'")

    if new_tier:
        from app.models.subscription_tier import SubscriptionTier
        tier_record = SubscriptionTier.query.filter_by(key=new_tier).first()
        if tier_record:
            print(f"DEBUG: Updating organization tier to '{new_tier}'")
            org.subscription_tier_id = tier_record.id
        else:
            print(f"DEBUG: Tier '{new_tier}' not found in database")

    try:
        db.session.commit()
        print(f"DEBUG: Successfully committed changes")
        print(f"DEBUG: Name: '{old_name}' -> '{org.name}'")
        print(f"DEBUG: Active: {old_active} -> {org.is_active}")
        print(f"DEBUG: New effective tier: '{org.effective_subscription_tier}'")
        flash('Organization updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG: Error committing changes: {str(e)}")
        flash(f'Error updating organization: {str(e)}', 'error')

    return redirect(url_for('developer.organization_detail', org_id=org_id))

@developer_bp.route('/organizations/<int:org_id>/upgrade', methods=['POST'])
@login_required
def upgrade_organization(org_id):
    """Upgrade organization subscription"""
    org = Organization.query.get_or_404(org_id)
    new_tier = request.form.get('tier')

    from app.models.subscription_tier import SubscriptionTier
    tier_record = SubscriptionTier.query.filter_by(key=new_tier).first()

    if tier_record:
        org.subscription_tier_id = tier_record.id
        db.session.commit()
        flash(f'Organization upgraded to {new_tier}', 'success')
    else:
        flash('Invalid subscription tier', 'error')

    return redirect(url_for('developer.organization_detail', org_id=org_id))

@developer_bp.route('/organizations/<int:org_id>/delete', methods=['POST'])
@login_required
def delete_organization(org_id):
    """Permanently delete an organization and all associated data (developers only)"""
    try:
        data = request.get_json()
        password = data.get('password')
        confirm_text = data.get('confirm_text')

        org = Organization.query.get_or_404(org_id)
        expected_confirm = f"DELETE {org.name}"

        # Validate developer password
        if not current_user.check_password(password):
            return jsonify({'success': False, 'error': 'Invalid developer password'})

        # Validate confirmation text
        if confirm_text != expected_confirm:
            return jsonify({'success': False, 'error': f'Confirmation text must match exactly: "{expected_confirm}"'})

        # Security check - prevent deletion of organizations with active subscriptions
        # You might want to add additional checks here based on your business rules

        # Log the deletion attempt for security audit
        from datetime import datetime
        import logging
        logging.warning(f"ORGANIZATION DELETION: Developer {current_user.username} is deleting organization '{org.name}' (ID: {org.id}) at {datetime.utcnow()}")

        # Begin deletion process
        org_name = org.name
        users_count = len(org.users)

        # Delete all organization data in the correct order to respect foreign key constraints

        # 1. Delete user role assignments
        from app.models.user_role_assignment import UserRoleAssignment
        UserRoleAssignment.query.filter_by(organization_id=org_id).delete()

        # 2. Delete organization-specific roles
        from app.models.role import Role
        Role.query.filter_by(organization_id=org_id, is_system_role=False).delete()

        # 3. Delete batches and related data
        from app.models import Batch
        batches = Batch.query.filter_by(organization_id=org_id).all()
        for batch in batches:
            # Delete batch containers, timers, etc. if you have those relationships
            db.session.delete(batch)

        # 4. Delete inventory and FIFO history
        from app.models import InventoryItem, InventoryHistory
        inventory_items = InventoryItem.query.filter_by(organization_id=org_id).all()
        for item in inventory_items:
            # Delete associated inventory history (contains FIFO tracking)
            InventoryHistory.query.filter_by(inventory_item_id=item.id).delete()
            db.session.delete(item)

        # 5. Delete products and SKUs
        from app.models import Product
        products = Product.query.filter_by(organization_id=org_id).all()
        for product in products:
            # Delete product variants, SKUs, history, etc.
            db.session.delete(product)

        # 6. Delete recipes
        from app.models import Recipe
        Recipe.query.filter_by(organization_id=org_id).delete()

        # 7. Organization tier relationship will be handled by cascade delete

        # 8. Delete user preferences first, then users
        from app.models.user_preferences import UserPreferences

        org_users = User.query.filter_by(organization_id=org_id).all()
        for user in org_users:
            if user.user_type != 'developer':  # Don't delete developer accounts
                # Delete user preferences first
                UserPreferences.query.filter_by(user_id=user.id).delete()
                # Then delete the user
                db.session.delete(user)

        # 9. Finally delete the organization
        db.session.delete(org)

        # Commit all deletions
        db.session.commit()

        # Log successful deletion
        logging.warning(f"ORGANIZATION DELETED: '{org_name}' (ID: {org_id}) successfully deleted by developer {current_user.username}. {users_count} users removed.")

        return jsonify({
            'success': True, 
            'message': f'Organization "{org_name}" and all associated data permanently deleted. {users_count} users removed.'
        })

    except Exception as e:
        db.session.rollback()
        logging.error(f"ORGANIZATION DELETION FAILED: Error deleting organization {org_id}: {str(e)}")
        return jsonify({'success': False, 'error': f'Failed to delete organization: {str(e)}'})

@developer_bp.route('/users')
@login_required
def users():
    """User management dashboard"""
    # Get all users separated by type
    customer_users = User.query.filter(User.user_type != 'developer').all()
    developer_users = User.query.filter(User.user_type == 'developer').all()

    return render_template('developer/users.html',
                         customer_users=customer_users,
                         developer_users=developer_users)

@developer_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
def toggle_user_active(user_id):
    """Toggle user active status"""
    user = User.query.get_or_404(user_id)

    if user.user_type == 'developer':
        flash('Cannot modify developer users', 'error')
        return redirect(url_for('developer.users'))

    user.is_active = not user.is_active
    db.session.commit()

    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User {user.username} {status}', 'success')

    return redirect(url_for('developer.users'))

@developer_bp.route('/system')
@login_required
def system_settings():
    """System-wide settings and configuration"""
    # Get system statistics
    stats = {
        'total_permissions': Permission.query.count(),
        'total_roles': Role.query.count(),
        'total_organizations': Organization.query.count(),
        'total_users': User.query.count()
    }

    return render_template('developer/system_settings.html', stats=stats)

# Customer support filtering routes
@developer_bp.route('/select-org/<int:org_id>')
@login_required
def select_organization(org_id):
    """Select an organization to view as developer (customer support)"""
    org = Organization.query.get_or_404(org_id)
    session['dev_selected_org_id'] = org_id
    flash(f'Now viewing data for: {org.name} (Customer Support Mode)', 'info')
    return redirect(url_for('app_routes.dashboard'))

@developer_bp.route('/clear-org-filter')
@login_required
def clear_organization_filter():
    """Clear organization filter and view all data"""
    session.pop('dev_selected_org_id', None)
    flash('Organization filter cleared - viewing all data', 'info')
    return redirect(url_for('app_routes.dashboard'))

# API endpoints for dashboard
@developer_bp.route('/api/stats')
@login_required
def api_stats():
    """API endpoint for dashboard statistics"""
    stats = {
        'organizations': {
            'total': Organization.query.count(),
            'active': Organization.query.filter_by(is_active=True).count(),
            'by_tier': {}
        },
        'users': {
            'total': User.query.filter(User.user_type != 'developer').count(),
            'active': User.query.filter(
                User.user_type != 'developer',
                User.is_active == True
            ).count()
        }
    }

    # Subscription tier breakdown - get from SubscriptionTier model
    from app.models.subscription_tier import SubscriptionTier
    for tier in ['exempt', 'free', 'solo', 'team', 'enterprise']:
        tier_record = SubscriptionTier.query.filter_by(key=tier).first()
        if tier_record:
            stats['organizations']['by_tier'][tier] = Organization.query.filter_by(
                subscription_tier_id=tier_record.id
            ).count()
        else:
            stats['organizations']['by_tier'][tier] = 0

    return jsonify(stats)

# Enhanced User Management API Endpoints

@developer_bp.route('/api/user/<int:user_id>')
@login_required
def get_user_details(user_id):
    """Get detailed user information for editing"""
    try:
        user = User.query.get_or_404(user_id)

        # Don't allow developers to edit other developer accounts through this endpoint
        if user.user_type != 'developer':
            user_data = {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'phone': user.phone,
                'user_type': user.user_type,
                'is_active': user.is_active,
                'organization_id': user.organization_id,
                'organization_name': user.organization.name if user.organization else None,
                'last_login': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else None,
                'created_at': user.created_at.strftime('%Y-%m-%d') if user.created_at else None
            }
            return jsonify({'success': True, 'user': user_data})
        else:
            return jsonify({'success': False, 'error': 'Cannot edit developer users through this endpoint'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/api/developer-user/<int:user_id>')
@login_required
def get_developer_user_details(user_id):
    """Get detailed developer user information for editing"""
    try:
        user = User.query.get_or_404(user_id)

        if user.user_type == 'developer':
            # Get available developer roles
            from app.models.developer_role import DeveloperRole
            from app.models.user_role_assignment import UserRoleAssignment

            all_dev_roles = DeveloperRole.query.filter_by(is_active=True).all()
            user_role_assignments = UserRoleAssignment.query.filter_by(
                user_id=user_id,
                is_active=True
            ).filter(UserRoleAssignment.developer_role_id.isnot(None)).all()

            assigned_role_ids = [assignment.developer_role_id for assignment in user_role_assignments]

            roles_data = []
            for role in all_dev_roles:
                roles_data.append({
                    'id': role.id,
                    'name': role.name,
                    'description': role.description,
                    'assigned': role.id in assigned_role_ids
                })

            user_data = {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'phone': user.phone,
                'is_active': user.is_active,
                'last_login': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else None,
                'created_at': user.created_at.strftime('%Y-%m-%d') if user.created_at else None,
                'roles': roles_data
            }
            return jsonify({'success': True, 'user': user_data})
        else:
            return jsonify({'success': False, 'error': 'User is not a developer'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/api/user/update', methods=['POST'])
@login_required
def update_user():
    """Update user information"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        user = User.query.get_or_404(user_id)

        # Don't allow editing developer users through this endpoint
        if user.user_type == 'developer':
            return jsonify({'success': False, 'error': 'Cannot edit developer users through this endpoint'})

        # Update user fields
        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        user.email = data.get('email', user.email)
        user.phone = data.get('phone', user.phone)
        user.user_type = data.get('user_type', user.user_type)
        user.is_active = data.get('is_active', user.is_active)

        # Handle organization owner flag with single owner constraint and role transfer
        if 'is_organization_owner' in data:
            new_owner_status = data['is_organization_owner']
            transfer_role = data.get('transfer_owner_role', False)

            if new_owner_status and not user.is_organization_owner:
                # User is being made an organization owner
                # First, remove organization owner status and role from all other users in this org
                other_owners = User.query.filter(
                    User.organization_id == user.organization_id,
                    User.id != user.id,
                    User._is_organization_owner == True
                ).all()

                from app.models.role import Role
                org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()

                for other_owner in other_owners:
                    print(f"Removing owner status from user {other_owner.id} ({other_owner.username})")
                    other_owner.is_organization_owner = False
                    # Remove the organization owner role from other owners
                    if org_owner_role:
                        other_owner.remove_role(org_owner_role)

                # Now set this user as the owner and assign the role
                user.is_organization_owner = True
                print(f"Setting user {user.id} ({user.username}) as organization owner")

                # Ensure the organization owner role is assigned
                if org_owner_role:
                    user.assign_role(org_owner_role, assigned_by=current_user)
                    print(f"Assigned organization_owner role to user {user.id}")

            elif not new_owner_status and user.is_organization_owner:
                # User is being removed as organization owner
                print(f"Removing organization owner status from user {user.id} ({user.username})")
                user.is_organization_owner = False

                # Remove the organization owner role
                from app.models.role import Role
                org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
                if org_owner_role:
                    user.remove_role(org_owner_role)
                    print(f"Removed organization_owner role from user {user.id}")

        db.session.commit()

        return jsonify({'success': True, 'message': 'User updated successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/api/developer-user/update', methods=['POST'])
@login_required
def update_developer_user():
    """Update developer user information"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        user = User.query.get_or_404(user_id)

        if user.user_type != 'developer':
            return jsonify({'success': False, 'error': 'User is not a developer'})

        # Update user fields
        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        user.email = data.get('email', user.email)
        user.phone = data.get('phone', user.phone)
        user.is_active = data.get('is_active', user.is_active)

        # Update developer role assignments
        from app.models.user_role_assignment import UserRoleAssignment

        # Deactivate existing developer role assignments
        existing_assignments = UserRoleAssignment.query.filter_by(
            user_id=user_id,
            is_active=True
        ).filter(UserRoleAssignment.developer_role_id.isnot(None)).all()

        for assignment in existing_assignments:
            assignment.is_active = False

        # Add new role assignments
        new_role_ids = data.get('roles', [])
        for role_id in new_role_ids:
            # Check if assignment already exists
            existing = UserRoleAssignment.query.filter_by(
                user_id=user_id,
                developer_role_id=role_id
            ).first()

            if existing:
                existing.is_active = True
                existing.assigned_at = datetime.utcnow()
                existing.assigned_by = current_user.id
            else:
                new_assignment = UserRoleAssignment(
                    user_id=user_id,
                    developer_role_id=role_id,
                    assigned_by=current_user.id,
                    is_active=True
                )
                db.session.add(new_assignment)

        db.session.commit()

        return jsonify({'success': True, 'message': 'Developer user updated successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/api/user/reset-password', methods=['POST'])
@login_required
def reset_user_password():
    """Reset user password"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        new_password = data.get('new_password')

        if not new_password:
            return jsonify({'success': False, 'error': 'New password is required'})

        user = User.query.get_or_404(user_id)
        user.set_password(new_password)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Password reset successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/api/user/soft-delete', methods=['POST'])
@login_required
def soft_delete_user():
    """Soft delete a user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        user = User.query.get_or_404(user_id)

        # Don't allow soft deleting developer users
        if user.user_type == 'developer':
            return jsonify({'success': False, 'error': 'Cannot soft delete developer users'})

        user.soft_delete(current_user)

        return jsonify({'success': True, 'message': 'User soft deleted successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/login-as/<int:user_id>')
@login_required
def login_as_user(user_id):
    """Login as another user for customer support"""
    try:
        target_user = User.query.get_or_404(user_id)

        # Don't allow logging in as other developers
        if target_user.user_type == 'developer':
            flash('Cannot login as another developer user', 'error')
            return redirect(url_for('developer.users'))

        # Log this action for security audit
        import logging
        logging.warning(f"DEVELOPER LOGIN AS USER: Developer {current_user.username} logged in as user {target_user.username} (ID: {target_user.id})")

        # Store the original developer user in session before switching
        session['original_developer_id'] = current_user.id
        session['is_developer_impersonation'] = True

        # Login as the target user
        from flask_login import login_user
        login_user(target_user)

        flash(f'Logged in as {target_user.username} (Developer Impersonation Mode)', 'info')
        return redirect(url_for('app_routes.dashboard'))

    except Exception as e:
        flash(f'Error logging in as user: {str(e)}', 'error')
        return redirect(url_for('developer.users'))

@developer_bp.route('/api/user/<int:user_id>')
@login_required
def get_user_api(user_id):
    """Get user data for management modal"""
    try:
        user = User.query.get_or_404(user_id)

        # Get the actual organization owner status
        is_org_owner = getattr(user, 'is_organization_owner', False)

        user_data = {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'phone': user.phone,
            'user_type': user.user_type,
            'is_organization_owner': is_org_owner,
            '_is_organization_owner': getattr(user, '_is_organization_owner', False),  # Also include the private field
            'is_active': user.is_active,
            'display_role': user.display_role,  # Include display role for additional context
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None,
            'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else None,
            'organization': {
                'id': user.organization.id,
                'name': user.organization.name
            } if user.organization else None
        }

        # Debug logging
        print(f"API returning user {user_id} with is_organization_owner: {is_org_owner}")

        return jsonify({'success': True, 'user': user_data})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})