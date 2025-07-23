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

    # Subscription tier breakdown
    subscription_stats = db.session.query(
        Organization.subscription_tier,
        func.count(Organization.id).label('count')
    ).group_by(Organization.subscription_tier).all()

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
    if request.method == 'POST':
        # Organization details
        name = request.form.get('name')
        subscription_tier = request.form.get('subscription_tier', 'free')

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
                subscription_tier=subscription_tier,
                contact_email=email,
                is_active=True
            )
            db.session.add(org)
            db.session.flush()  # Get the ID

            # Create organization owner user
            owner_user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                organization_id=org.id,
                user_type='organization_owner',
                is_active=True
            )
            owner_user.set_password(password)
            db.session.add(owner_user)
            db.session.commit()

            flash(f'Organization "{name}" and owner user "{username}" created successfully', 'success')
            return redirect(url_for('developer.organization_detail', org_id=org.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating organization: {str(e)}', 'error')
            return redirect(url_for('developer.create_organization'))

    return render_template('developer/create_organization.html')

@developer_bp.route('/organizations/<int:org_id>')
@login_required
def organization_detail(org_id):
    """Detailed organization management"""
    org = Organization.query.get_or_404(org_id)
    users = User.query.filter_by(organization_id=org_id).all()

    return render_template('developer/organization_detail.html',
                         organization=org,
                         users=users)

@developer_bp.route('/organizations/<int:org_id>/edit', methods=['POST'])
@login_required
def edit_organization(org_id):
    """Edit organization details"""
    org = Organization.query.get_or_404(org_id)

    org.name = request.form.get('name', org.name)
    org.subscription_tier = request.form.get('subscription_tier', org.subscription_tier)
    org.is_active = request.form.get('is_active') == 'true'

    db.session.commit()
    flash('Organization updated successfully', 'success')

    return redirect(url_for('developer.organization_detail', org_id=org_id))

@developer_bp.route('/organizations/<int:org_id>/upgrade', methods=['POST'])
@login_required
def upgrade_organization(org_id):
    """Upgrade organization subscription"""
    org = Organization.query.get_or_404(org_id)
    new_tier = request.form.get('tier')

    if new_tier in ['free', 'solo', 'team', 'enterprise']:
        org.subscription_tier = new_tier
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

        # 7. Delete subscriptions
        from app.models.subscription import Subscription
        Subscription.query.filter_by(organization_id=org_id).delete()

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
    """User management page for developers"""
    if current_user.user_type != 'developer':
        flash('Access denied', 'error')
        return redirect(url_for('app_routes.dashboard'))

    # Get all customer users (non-developers)
    customer_users = User.query.filter(
        User.user_type != 'developer',
        User.is_deleted == False
    ).all()

    # Get all developer users
    developer_users = User.query.filter(
        User.user_type == 'developer',
        User.is_deleted == False
    ).all()

    # Get developer roles for the modal
    from app.models.developer_role import DeveloperRole
    developer_roles = DeveloperRole.query.filter_by(is_active=True).all()

    return render_template('developer/users.html', 
                         customer_users=customer_users,
                         developer_users=developer_users,
                         developer_roles=developer_roles)

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

    # Subscription tier breakdown
    for tier in ['free', 'solo', 'team', 'enterprise']:
        stats['organizations']['by_tier'][tier] = Organization.query.filter_by(
            subscription_tier=tier
        ).count()

    return jsonify(stats)



# Customer User Role Management
@developer_bp.route('/customer-users/<int:user_id>/roles', methods=['GET'])
@login_required
def get_customer_user_roles(user_id):
    """Get current roles for a customer user"""
    if current_user.user_type != 'developer':
        return jsonify({'error': 'Access denied'}), 403

    user = User.query.filter_by(id=user_id, user_type='customer').first_or_404()
    current_roles = [assignment.role_id for assignment in user.role_assignments if assignment.is_active and assignment.role_id]

    return jsonify({
        'success': True,
        'current_roles': current_roles
    })

@developer_bp.route('/customer-users/<int:user_id>/available-roles', methods=['GET'])
@login_required
def get_customer_user_available_roles(user_id):
    """Get available roles for a customer user"""
    if current_user.user_type != 'developer':
        return jsonify({'error': 'Access denied'}), 403

    user = User.query.filter_by(id=user_id, user_type='customer').first_or_404()

    if not user.organization_id:
        return jsonify({'error': 'User must belong to an organization'}), 400

    # Get system roles that apply to this organization
    from app.models.role import Role
    available_roles = Role.query.filter_by(is_system_role=True, is_active=True).all()

    roles_data = []
    for role in available_roles:
        roles_data.append({
            'id': role.id,
            'name': role.name,
            'description': role.description
        })

    return jsonify({
        'success': True,
        'roles': roles_data
    })

@developer_bp.route('/customer-users/<int:user_id>/validate-org-owner', methods=['GET'])
@login_required
def validate_org_owner_assignment(user_id):
    """Validate if organization owner can be assigned"""
    if current_user.user_type != 'developer':
        return jsonify({'error': 'Access denied'}), 403

    user = User.query.filter_by(id=user_id, user_type='customer').first_or_404()

    if not user.organization_id:
        return jsonify({
            'can_assign': False,
            'message': 'User must belong to an organization to be an organization owner'
        })

    # Check if there's already an organization owner
    from app.models.role import Role
    from app.models.user_role_assignment import UserRoleAssignment

    org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
    if not org_owner_role:
        return jsonify({
            'can_assign': False,
            'message': 'Organization owner role not found'
        })

    existing_owner = UserRoleAssignment.query.filter_by(
        role_id=org_owner_role.id,
        organization_id=user.organization_id,
        is_active=True
    ).filter(UserRoleAssignment.user_id != user.id).first()

    if existing_owner:
        existing_user = User.query.get(existing_owner.user_id)
        return jsonify({
            'can_assign': False,
            'message': f'Organization already has an owner: {existing_user.username if existing_user else "Unknown user"}'
        })

    return jsonify({
        'can_assign': True,
        'message': 'Organization owner can be assigned'
    })

@developer_bp.route('/customer-users/<int:user_id>/roles', methods=['PUT'])
@login_required
def update_customer_user_roles(user_id):
    """Update roles for a customer user"""
    if current_user.user_type != 'developer':
        return jsonify({'error': 'Access denied'}), 403

    try:
        user = User.query.filter_by(id=user_id, user_type='customer').first_or_404()
        data = request.get_json()
        role_ids = data.get('role_ids', [])

        if not user.organization_id:
            return jsonify({'error': 'User must belong to an organization'}), 400

        # Validate organization owner assignment
        from app.models.role import Role
        from app.models.user_role_assignment import UserRoleAssignment

        org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
        if org_owner_role and org_owner_role.id in role_ids:
            existing_owner = UserRoleAssignment.query.filter_by(
                role_id=org_owner_role.id,
                organization_id=user.organization_id,
                is_active=True
            ).filter(UserRoleAssignment.user_id != user.id).first()

            if existing_owner:
                existing_user = User.query.get(existing_owner.user_id)
                return jsonify({
                    'success': False,
                    'error': f'Organization already has an owner: {existing_user.username if existing_user else "Unknown user"}'
                })

        # Deactivate existing role assignments
        existing_assignments = UserRoleAssignment.query.filter_by(
            user_id=user.id,
            organization_id=user.organization_id,
            is_active=True
        ).filter(UserRoleAssignment.role_id.isnot(None)).all()

        for assignment in existing_assignments:
            assignment.is_active = False

        # Add new role assignments
        for role_id in role_ids:
            role = Role.query.filter_by(id=role_id, is_system_role=True).first()
            if role:
                assignment = UserRoleAssignment(
                    user_id=user.id,
                    role_id=role.id,
                    organization_id=user.organization_id,
                    assigned_by=current_user.id,
                    is_active=True
                )
                db.session.add(assignment)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Roles updated for user {user.username}'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        })