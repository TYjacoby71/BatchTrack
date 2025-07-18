
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Organization, User, Permission, Role
from app.extensions import db
from datetime import datetime, timedelta
from sqlalchemy import func

developer_bp = Blueprint('developer', __name__, url_prefix='/developer')

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

@developer_bp.route('/subscriptions')
@login_required
def subscription_management():
    """Subscription and billing management"""
    # Group organizations by subscription tier
    tiers = {}
    for tier in ['free', 'solo', 'team', 'enterprise']:
        orgs = Organization.query.filter_by(subscription_tier=tier).all()
        tiers[tier] = {
            'count': len(orgs),
            'organizations': orgs
        }
    
    return render_template('developer/subscriptions.html', tiers=tiers)

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
