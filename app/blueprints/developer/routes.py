from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Organization, User, Permission, Role, GlobalItem
from app.models import ProductCategory
from app.extensions import db
from datetime import datetime, timedelta
from sqlalchemy import func
from .system_roles import system_roles_bp
from .subscription_tiers import subscription_tiers_bp

# Assuming require_developer_permission is defined elsewhere, e.g., in system_roles.py or utils.py
# If not, you'll need to define or import it. For now, let's assume it's available.
# If you are using @login_required, you might not need @require_developer_permission for all routes
# but for the waitlist statistics, it seems intended.
# For demonstration, if require_developer_permission is not defined, you can temporarily remove it
# or define a placeholder. Let's assume it's correctly imported or defined.
try:
    from .decorators import require_developer_permission, permission_required
except ImportError:
    # Define a placeholder if not found, to allow the rest of the code to be processed
    # In a real scenario, ensure this decorator is correctly imported.
    def require_developer_permission(permission_name):
        def decorator(func):
            return func
        return decorator
    def permission_required(permission_name):
        def decorator(func):
            return func
        return decorator

# Assuming TimezoneUtils is available and correctly imported
try:
    from app.utils.timezone_utils import TimezoneUtils
except ImportError:
    # Define a placeholder if not found
    class TimezoneUtils:
        @staticmethod
        def utc_now():
            return datetime.utcnow()

developer_bp = Blueprint('developer', __name__, url_prefix='/developer')
developer_bp.register_blueprint(system_roles_bp)
developer_bp.register_blueprint(subscription_tiers_bp)
from .addons import addons_bp
developer_bp.register_blueprint(addons_bp)

# Developer access control is handled centrally in `app/middleware.py`.
# This eliminates the dual security checkpoints that were causing routing conflicts

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
        SubscriptionTier.name,
        func.count(Organization.id).label('count')
    ).join(Organization, Organization.subscription_tier_id == SubscriptionTier.id).group_by(SubscriptionTier.name).all()

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

    # Get waitlist count
    import json
    import os
    waitlist_count = 0
    waitlist_file = 'data/waitlist.json'
    if os.path.exists(waitlist_file):
        try:
            with open(waitlist_file, 'r') as f:
                waitlist_data = json.load(f)
                waitlist_count = len(waitlist_data)
        except (json.JSONDecodeError, IOError):
            waitlist_count = 0

    return render_template('developer/dashboard.html',
                         total_orgs=total_orgs,
                         active_orgs=active_orgs,
                         total_users=total_users,
                         active_users=active_users,
                         subscription_stats=subscription_stats,
                         recent_orgs=recent_orgs,
                         problem_orgs=problem_orgs,
                         waitlist_count=waitlist_count)

@developer_bp.route('/marketing-admin')
@login_required
def marketing_admin():
    """Manage homepage marketing content (reviews, spotlights, messages)."""
    import json, os
    reviews = []
    spotlights = []
    messages = {'day_1': '', 'day_3': '', 'day_5': ''}
    promo_codes = []
    demo_url = ''
    demo_videos = []
    try:
        if os.path.exists('data/reviews.json'):
            with open('data/reviews.json', 'r') as f:
                reviews = json.load(f) or []
    except Exception:
        reviews = []
    try:
        if os.path.exists('data/spotlights.json'):
            with open('data/spotlights.json', 'r') as f:
                spotlights = json.load(f) or []
    except Exception:
        spotlights = []
    try:
        if os.path.exists('settings.json'):
            with open('settings.json', 'r') as f:
                cfg = json.load(f) or {}
                messages.update(cfg.get('marketing_messages', {}))
                promo_codes = cfg.get('promo_codes', []) or []
                demo_url = cfg.get('demo_url', '') or ''
                demo_videos = cfg.get('demo_videos', []) or []
    except Exception:
        pass
    return render_template('developer/marketing_admin.html', reviews=reviews, spotlights=spotlights, messages=messages, promo_codes=promo_codes, demo_url=demo_url, demo_videos=demo_videos)

@developer_bp.route('/marketing-admin/save', methods=['POST'])
@login_required
def marketing_admin_save():
    """Save reviews, spotlights, and marketing messages (simple JSON persistence)."""
    try:
        import json
        data = request.get_json() or {}
        if 'reviews' in data:
            with open('data/reviews.json', 'w') as f:
                json.dump(data['reviews'], f, indent=2)
        if 'spotlights' in data:
            with open('data/spotlights.json', 'w') as f:
                json.dump(data['spotlights'], f, indent=2)
        if 'messages' in data or 'promo_codes' in data or 'demo_url' in data or 'demo_videos' in data:
            # merge into settings.json under marketing_messages
            try:
                with open('settings.json', 'r') as f:
                    cfg = json.load(f) or {}
            except FileNotFoundError:
                cfg = {}
            if 'messages' in data:
                cfg['marketing_messages'] = data['messages']
            if 'promo_codes' in data:
                cfg['promo_codes'] = data['promo_codes']
            if 'demo_url' in data:
                cfg['demo_url'] = data['demo_url']
            if 'demo_videos' in data:
                cfg['demo_videos'] = data['demo_videos']
            with open('settings.json', 'w') as f:
                json.dump(cfg, f, indent=2)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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
    # Load available tiers for the form (DB only)
    from ..models.subscription_tier import SubscriptionTier as _ST
    available_tiers = {str(t.id): {'name': t.name} for t in _ST.query.order_by(_ST.name).all()}

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

    # Build subscription tiers from DB for the dropdown
    from ..models.subscription_tier import SubscriptionTier as _ST
    try:
        all_db_tiers = _ST.query.order_by(_ST.name).all()
        tiers_config = {str(t.id): {'name': t.name, 'is_available': t.has_valid_integration or t.is_billing_exempt} for t in all_db_tiers}
    except Exception:
        tiers_config = {}

    # Debug subscription info
    current_tier = org.effective_subscription_tier
    tier_record = org.tier

    print(f"DEBUG: Organization {org.name} (ID: {org.id})")
    print(f"DEBUG: Has tier record: {tier_record is not None}")
    if tier_record:
        print(f"DEBUG: Tier id: {tier_record.id}")
        print(f"DEBUG: Tier name: {tier_record.name}")
    print(f"DEBUG: Effective tier id: {current_tier}")
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

        # Import all models needed for deletion
        from app.models import (
            User, Batch, BatchIngredient, BatchContainer, ExtraBatchContainer, 
            ExtraBatchIngredient, BatchTimer, Recipe, RecipeIngredient, 
            InventoryItem, Category, Role, Permission, ProductSKU, Product,
            Organization
        )
        from app.models.reservation import Reservation
        from app.models.subscription_tier import Subscription
        from app.models.user_role_assignment import UserRoleAssignment

        # Delete in proper order to avoid foreign key violations

        # 1. Delete batch-related data first (most dependent)
        ExtraBatchContainer.query.filter_by(organization_id=org_id).delete()
        ExtraBatchIngredient.query.filter_by(organization_id=org_id).delete()
        BatchContainer.query.filter_by(organization_id=org_id).delete()
        BatchIngredient.query.filter_by(organization_id=org_id).delete()
        BatchTimer.query.filter_by(organization_id=org_id).delete()

        # 2. Delete batches
        Batch.query.filter_by(organization_id=org_id).delete()

        # 3. Delete recipe ingredients, then recipes
        recipe_ids = [r.id for r in Recipe.query.filter_by(organization_id=org_id).all()]
        if recipe_ids:
            RecipeIngredient.query.filter(RecipeIngredient.recipe_id.in_(recipe_ids)).delete()
        Recipe.query.filter_by(organization_id=org_id).delete()

        # 4. Delete reservations
        Reservation.query.filter_by(organization_id=org_id).delete()

        # 5. Delete product-related data
        ProductSKU.query.filter_by(organization_id=org_id).delete()
        Product.query.filter_by(organization_id=org_id).delete()

        # 6. Delete inventory items
        InventoryItem.query.filter_by(organization_id=org_id).delete()

        # 7. Delete categories
        Category.query.filter_by(organization_id=org_id).delete()

        # 8. Delete user role assignments for org users
        org_user_ids = [u.id for u in User.query.filter_by(organization_id=org_id).all()]
        if org_user_ids:
            UserRoleAssignment.query.filter(UserRoleAssignment.user_id.in_(org_user_ids)).delete()

        # 9. Delete organization-specific roles (not system roles)
        Role.query.filter_by(organization_id=org_id, is_system_role=False).delete()

        # 10. Delete subscription
        subscription = Subscription.query.filter_by(organization_id=org_id).first()
        if subscription:
            db.session.delete(subscription)

        # 11. Delete users (this will handle the foreign key to organization)
        User.query.filter_by(organization_id=org_id).delete()

        # 12. Finally delete the organization itself
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

@developer_bp.route('/system-settings')
@require_developer_permission('system_admin')
def system_settings():
    """System settings and configuration"""
    # Get system statistics
    stats = {
        'total_permissions': Permission.query.count(),
        'total_roles': Role.query.count(),
        'total_organizations': Organization.query.count(),
        'total_users': User.query.count()
    }

    return render_template('developer/system_settings.html', stats=stats)

@developer_bp.route('/global-items')
@login_required
def global_items_admin():
    """Developer admin page for managing Global Items"""
    # Get filter parameters
    item_type = request.args.get('type', '').strip()
    category_filter = request.args.get('category', '').strip()
    search_query = request.args.get('search', '').strip()

    # Build base query (exclude archived)
    query = GlobalItem.query.filter(GlobalItem.is_archived != True)

    # Filter by item type if specified
    if item_type:
        query = query.filter(GlobalItem.item_type == item_type)

    # Filter by ingredient category name if specified (join via ingredient_category_id)
    if category_filter and item_type == 'ingredient':
        from app.models.category import IngredientCategory
        query = query.join(
            IngredientCategory, GlobalItem.ingredient_category_id == IngredientCategory.id
        ).filter(IngredientCategory.name == category_filter)

    # Add search functionality across name and aliases
    if search_query:
        term = f"%{search_query}%"
        try:
            # Prefer alias table when available
            from sqlalchemy import or_, exists, and_
            _alias_tbl = db.Table('global_item_alias', db.metadata, autoload_with=db.engine)
            query = query.filter(
                or_(
                    GlobalItem.name.ilike(term),
                    exists().where(and_(_alias_tbl.c.global_item_id == GlobalItem.id, _alias_tbl.c.alias.ilike(term)))
                )
            )
        except Exception:
            # Fallback to name-only search
            query = query.filter(GlobalItem.name.ilike(term))

    # Get filtered results
    items = query.order_by(GlobalItem.item_type.asc(), GlobalItem.name.asc()).limit(500).all()

    # Get unique ingredient categories for filter dropdown (ingredients only, global scope)
    from app.models.category import IngredientCategory
    categories = []
    try:
        categories = [
            name for (name,) in db.session.query(IngredientCategory.name)
            .join(GlobalItem, GlobalItem.ingredient_category_id == IngredientCategory.id)
            .filter(
                IngredientCategory.organization_id == None,  # global categories
                IngredientCategory.is_global_category == True,
                GlobalItem.item_type == 'ingredient'
            )
            .distinct()
            .order_by(IngredientCategory.name)
            .all()
            if name
        ]
    except Exception:
        # Safe fallback: list all global categories
        categories = [c.name for c in IngredientCategory.query.filter_by(
            organization_id=None, is_active=True, is_global_category=True
        ).order_by(IngredientCategory.name).all()]

    return render_template(
        'developer/global_items.html',
        items=items,
        categories=categories,
        selected_type=item_type,
        selected_category=category_filter,
        search_query=search_query,
    )

@developer_bp.route('/global-items/<int:item_id>')
@login_required
def global_item_detail(item_id):
    item = GlobalItem.query.get_or_404(item_id)

    # Get available global ingredient categories from IngredientCategory table
    from app.models.category import IngredientCategory
    global_ingredient_categories = IngredientCategory.query.filter_by(
        organization_id=None,
        is_active=True,
        is_global_category=True
    ).order_by(IngredientCategory.name).all()

    return render_template('developer/global_item_detail.html', item=item, global_ingredient_categories=global_ingredient_categories)

@developer_bp.route('/global-items/<int:item_id>/edit', methods=['POST'])
@login_required
def global_item_edit(item_id):
    """Edit existing global item"""
    # Add CSRF protection
    from flask_wtf.csrf import validate_csrf
    try:
        validate_csrf(request.form.get('csrf_token'))
    except Exception as e:
        flash(f"CSRF validation failed: {e}", "error")
        return redirect(url_for('developer.global_item_detail', item_id=item_id))

    item = GlobalItem.query.get_or_404(item_id)

    before = {
        'name': item.name,
        'item_type': item.item_type,
        'default_unit': item.default_unit,
        'density': item.density,
        'capacity': item.capacity,
        'capacity_unit': item.capacity_unit,
        'container_material': getattr(item, 'container_material', None),
        'container_type': getattr(item, 'container_type', None),
        'container_style': getattr(item, 'container_style', None),
        'default_is_perishable': item.default_is_perishable,
        'recommended_shelf_life_days': item.recommended_shelf_life_days,
        'aka_names': item.aka_names,
    }

    # Apply edits
    item.name = request.form.get('name', item.name)
    item.item_type = request.form.get('item_type', item.item_type)
    item.default_unit = request.form.get('default_unit', item.default_unit)
    density = request.form.get('density')
    item.density = float(density) if density not in (None, '',) else None
    capacity = request.form.get('capacity')
    item.capacity = float(capacity) if capacity not in (None, '',) else None
    item.capacity_unit = request.form.get('capacity_unit', item.capacity_unit)
    # Container attributes (optional)
    try:
        item.container_material = (request.form.get('container_material') or '').strip() or None
        item.container_type = (request.form.get('container_type') or '').strip() or None
        item.container_style = (request.form.get('container_style') or '').strip() or None
        item.container_color = (request.form.get('container_color') or '').strip() or None
    except Exception:
        pass
    item.default_is_perishable = True if request.form.get('default_is_perishable') == 'on' else False
    rsl = request.form.get('recommended_shelf_life_days')
    item.recommended_shelf_life_days = int(rsl) if rsl not in (None, '',) else None
    aka_names = request.form.get('aka_names')  # comma-separated
    if aka_names is not None:
        item.aka_names = [n.strip() for n in aka_names.split(',') if n.strip()]

    # Handle ingredient category - use the ID directly
    ingredient_category_id = request.form.get('ingredient_category_id', '').strip()
    if ingredient_category_id and ingredient_category_id.isdigit():
        # Verify the category exists (global scope)
        from app.models.category import IngredientCategory
        category = IngredientCategory.query.filter_by(
            id=int(ingredient_category_id),
            organization_id=None,
            is_global_category=True
        ).first()
        if category:
            item.ingredient_category_id = category.id
        else:
            item.ingredient_category_id = None
    else:
        item.ingredient_category_id = None

    try:
        db.session.commit()
        # Basic audit log
        import logging
        logging.info(f"GLOBAL_ITEM_EDIT: user={current_user.id} item_id={item.id} before={before} after={{'name': item.name, 'item_type': item.item_type, 'container_material': item.container_material, 'container_type': item.container_type, 'container_style': item.container_style}}")
        flash('Global item updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating global item: {e}', 'error')

    return redirect(url_for('developer.global_item_detail', item_id=item.id))

@developer_bp.route('/global-items/<int:item_id>/stats')
@login_required
def global_item_stats_view(item_id):
    from app.services.statistics.global_item_stats import GlobalItemStatsService
    item = GlobalItem.query.get_or_404(item_id)
    stats = GlobalItemStatsService.get_rollup(item_id)
    return render_template('developer/global_item_stats.html', item=item, stats=stats)

@developer_bp.route('/reference-categories')
@login_required
def reference_categories():
    """Manage global ingredient categories"""
    # Get existing ingredient categories in global scope (ignore legacy flag)
    from app.models.category import IngredientCategory
    existing_categories = IngredientCategory.query.filter_by(
        organization_id=None,
        is_active=True,
        is_global_category=True
    ).order_by(IngredientCategory.name).all()

    categories = [cat.name for cat in existing_categories]

    # Get global items by category for counting
    global_items_by_category = {}
    category_densities = {}

    for category_obj in existing_categories:
        # Correctly filter GlobalItems using ingredient_category_id
        items = GlobalItem.query.filter_by(ingredient_category_id=category_obj.id, is_archived=False).all()
        global_items_by_category[category_obj.name] = items

        # Use the category's default density
        if category_obj.default_density:
            category_densities[category_obj.name] = category_obj.default_density

    return render_template('developer/reference_categories.html', 
                         categories=categories,
                         global_items_by_category=global_items_by_category,
                         category_densities=category_densities)

@developer_bp.route('/container-management')
@login_required
def container_management():
    """Container management page for curating materials, types, colors, styles"""
    # Load master lists from settings - these are the single source of truth
    curated_lists = load_curated_container_lists()
    
    return render_template('developer/container_management.html',
                         curated_materials=curated_lists['materials'],
                         curated_types=curated_lists['types'],
                         curated_styles=curated_lists['styles'],
                         curated_colors=curated_lists['colors'])

@developer_bp.route('/container-management/save-curated', methods=['POST'])
@login_required
def save_curated_container_lists():
    """Save curated container lists to settings.json"""
    try:
        data = request.get_json()
        curated_lists = data.get('curated_lists', {})
        
        # Validate the structure
        required_keys = ['materials', 'types', 'styles', 'colors']
        for key in required_keys:
            if key not in curated_lists or not isinstance(curated_lists[key], list):
                return jsonify({'success': False, 'error': f'Invalid or missing {key} list'})
        
        # Load current settings
        import json
        import os
        settings_file = 'settings.json'
        settings = {}
        
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
            except (json.JSONDecodeError, IOError):
                settings = {}
        
        # Update container curated lists
        if 'container_management' not in settings:
            settings['container_management'] = {}
        
        settings['container_management']['curated_lists'] = curated_lists
        
        # Save back to file
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=2)
        
        return jsonify({'success': True, 'message': 'Curated lists saved successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def load_curated_container_lists():
    """Load curated container lists from settings or return defaults with existing database values merged in"""
    try:
        import json
        import os
        settings_file = 'settings.json'
        
        if os.path.exists(settings_file):
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                curated_lists = settings.get('container_management', {}).get('curated_lists', {})
                
                # If we have saved curated lists, return them
                if curated_lists and all(key in curated_lists for key in ['materials', 'types', 'styles', 'colors']):
                    return curated_lists
    except:
        pass
    
    # First time setup: merge database values with defaults
    defaults = {
        'materials': [
            'Glass', 'PET Plastic', 'HDPE Plastic', 'PP Plastic', 'Aluminum', 
            'Tin', 'Steel', 'Paperboard', 'Cardboard', 'Silicone'
        ],
        'types': [
            'Jar', 'Bottle', 'Tin', 'Tube', 'Pump Bottle', 'Spray Bottle',
            'Dropper Bottle', 'Roll-on Bottle', 'Squeeze Bottle', 'Vial'
        ],
        'styles': [
            'Boston Round', 'Straight Sided', 'Wide Mouth', 'Narrow Mouth',
            'Cobalt Blue', 'Amber', 'Clear', 'Frosted'
        ],
        'colors': [
            'Clear', 'Amber', 'Cobalt Blue', 'Green', 'White', 'Black',
            'Frosted', 'Silver', 'Gold'
        ]
    }
    
    # Get existing values from database and merge with defaults
    try:
        from app.models.global_item import GlobalItem
        from app.extensions import db
        
        # Get existing materials
        materials = db.session.query(GlobalItem.container_material)\
            .filter(GlobalItem.container_material.isnot(None))\
            .distinct().all()
        existing_materials = [m[0] for m in materials if m[0] and m[0] not in defaults['materials']]
        
        # Get existing types
        types = db.session.query(GlobalItem.container_type)\
            .filter(GlobalItem.container_type.isnot(None))\
            .distinct().all()
        existing_types = [t[0] for t in types if t[0] and t[0] not in defaults['types']]
        
        # Get existing styles
        styles = db.session.query(GlobalItem.container_style)\
            .filter(GlobalItem.container_style.isnot(None))\
            .distinct().all()
        existing_styles = [s[0] for s in styles if s[0] and s[0] not in defaults['styles']]
        
        # Get existing colors
        colors = db.session.query(GlobalItem.container_color)\
            .filter(GlobalItem.container_color.isnot(None))\
            .distinct().all()
        existing_colors = [c[0] for c in colors if c[0] and c[0] not in defaults['colors']]
        
        # Merge and sort
        defaults['materials'].extend(existing_materials)
        defaults['materials'] = sorted(list(set(defaults['materials'])))
        
        defaults['types'].extend(existing_types)
        defaults['types'] = sorted(list(set(defaults['types'])))
        
        defaults['styles'].extend(existing_styles)
        defaults['styles'] = sorted(list(set(defaults['styles'])))
        
        defaults['colors'].extend(existing_colors)
        defaults['colors'] = sorted(list(set(defaults['colors'])))
        
    except Exception:
        pass  # Use defaults if database query fails
    
    return defaults

@developer_bp.route('/system-statistics')
@login_required
def system_statistics():
    """System-wide statistics dashboard"""
    # Gather system statistics
    stats = {
        'total_organizations': Organization.query.count(),
        'active_organizations': Organization.query.filter_by(is_active=True).count(),
        'total_users': User.query.filter(User.user_type != 'developer').count(),
        'active_users': User.query.filter(
            User.user_type != 'developer',
            User.is_active == True
        ).count(),
        'total_global_items': GlobalItem.query.filter_by(is_archived=False).count(),
        'total_permissions': Permission.query.count(),
        'total_roles': Role.query.count()
    }
    
    return render_template('developer/system_statistics.html', stats=stats)

@developer_bp.route('/billing-integration')
@login_required
def billing_integration():
    """Billing integration management"""
    return render_template('developer/billing_integration.html')

@developer_bp.route('/reference-categories/add', methods=['POST'])
@login_required
def add_reference_category():
    """Add a new global ingredient category"""
    try:
        data = request.get_json()
        category_name = data.get('name', '').strip()
        default_density = data.get('default_density', None)

        if not category_name:
            return jsonify({'success': False, 'error': 'Category name is required'})

        # Check if category already exists
        from app.models.category import IngredientCategory
        existing = IngredientCategory.query.filter_by(
            name=category_name,
            organization_id=None
        ).first()

        if existing:
            return jsonify({'success': False, 'error': 'Category already exists'})

        # Create new ingredient category
        new_category = IngredientCategory(
            name=category_name,
            is_global_category=True,
            organization_id=None,
            is_active=True,
            default_density=default_density if isinstance(default_density, (int, float)) else None
        )

        db.session.add(new_category)
        db.session.commit()

        return jsonify({'success': True, 'message': f'Category "{category_name}" added successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/reference-categories/delete', methods=['POST'])
@login_required
def delete_reference_category():
    """Delete a global ingredient category"""
    try:
        data = request.get_json()
        category_name = data.get('name', '').strip()

        if not category_name:
            return jsonify({'success': False, 'error': 'Category name is required'})

        # Find the category
        from app.models.category import IngredientCategory
        category = IngredientCategory.query.filter_by(
            name=category_name,
            organization_id=None
        ).first()

        if not category:
            return jsonify({'success': False, 'error': 'Category not found'})

        # Count items using this category
        items_count = GlobalItem.query.filter_by(
            ingredient_category_id=category.id, # Use the correct foreign key
            is_archived=False
        ).count()

        if items_count > 0:
            return jsonify({
                'success': False, 
                'error': f'Cannot delete category. {items_count} active items are using this category.'
            })

        # Delete the category
        db.session.delete(category)
        db.session.commit()

        return jsonify({'success': True, 'message': f'Category "{category_name}" deleted successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/reference-categories/update-density', methods=['POST'])
@login_required
def update_category_density():
    """Update the default density for a global ingredient category"""
    try:
        data = request.get_json()
        category_name = data.get('category', '').strip()
        density = data.get('density')

        if not category_name:
            return jsonify({'success': False, 'error': 'Category name is required'})

        # Find the category
        from app.models.category import IngredientCategory
        category = IngredientCategory.query.filter_by(
            name=category_name,
            organization_id=None
        ).first()

        if not category:
            return jsonify({'success': False, 'error': 'Category not found'})

        # Update the category's default density
        try:
            density_value = float(density) if density is not None else None
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'Invalid density value'}), 400

        if density_value is not None and density_value >= 0: # Allow 0 density
            category.default_density = density_value

            # Optionally update items that don't have specific densities
            items = GlobalItem.query.filter_by(ingredient_category_id=category.id, is_archived=False).all()
            for item in items:
                if item.density is None or item.density == 0:
                    item.density = density

        db.session.commit()

        return jsonify({
            'success': True, 
            'message': f'Density updated for category "{category_name}"',
            'density': category.default_density
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/reference-categories/calculate-density', methods=['POST'])
@login_required
def calculate_category_density():
    """Calculate average density for a category based on its items"""
    try:
        data = request.get_json()
        category_name = data.get('category', '').strip()

        if not category_name:
            return jsonify({'success': False, 'error': 'Category name is required'})

        # Get the category object to find its ID
        from app.models.category import IngredientCategory
        category = IngredientCategory.query.filter_by(name=category_name, organization_id=None).first()

        if not category:
            return jsonify({'success': False, 'error': 'Category not found'})

        # Get all items in this category with valid densities
        items = GlobalItem.query.filter_by(ingredient_category_id=category.id, is_archived=False).all()
        densities = [item.density for item in items if item.density is not None and item.density > 0]

        if not densities:
            return jsonify({
                'success': False, 
                'error': 'No items with valid density values found in this category'
            })

        calculated_density = sum(densities) / len(densities)

        return jsonify({
            'success': True, 
            'calculated_density': calculated_density,
            'items_count': len(densities),
            'message': f'Calculated density: {calculated_density:.3f} g/ml from {len(densities)} items'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/global-items/create', methods=['GET', 'POST'])
@login_required
def create_global_item():
    """Create a new global item"""
    if request.method == 'POST':
        try:
            # Extract form data
            name = request.form.get('name', '').strip()
            item_type = request.form.get('item_type', 'ingredient')
            default_unit = request.form.get('default_unit', '').strip() or None
            # Get ingredient category id from form
            ingredient_category_id_str = request.form.get('ingredient_category_id', '').strip() or None

            # Validation
            if not name:
                flash('Name is required', 'error')
                return redirect(url_for('developer.create_global_item'))

            # Validate ingredient_category_id
            ingredient_category_id = None
            if ingredient_category_id_str:
                if ingredient_category_id_str.isdigit():
                    # Verify the category exists and is a global ingredient category
                    from app.models.category import IngredientCategory
                    category = IngredientCategory.query.filter_by(
                        id=int(ingredient_category_id_str),
                        organization_id=None,  # Global categories are global
                        is_global_category=True
                    ).first()
                    if category:
                        ingredient_category_id = category.id
                    else:
                        flash(f'Ingredient category ID "{ingredient_category_id_str}" not found or is not a valid reference category.', 'error')
                        return redirect(url_for('developer.create_global_item'))
                else:
                    flash(f'Invalid Ingredient Category ID format: "{ingredient_category_id_str}"', 'error')
                    return redirect(url_for('developer.create_global_item'))

            # Check for duplicate
            existing = GlobalItem.query.filter_by(name=name, item_type=item_type).first()
            if existing and not existing.is_archived:
                flash(f'Global item "{name}" of type "{item_type}" already exists', 'error')
                return redirect(url_for('developer.create_global_item'))

            # Create new global item
            new_item = GlobalItem(
                name=name,
                item_type=item_type,
                default_unit=default_unit,
                ingredient_category_id=ingredient_category_id
            )

            # Add optional fields
            density = request.form.get('density')
            if density:
                try:
                    new_item.density = float(density)
                except ValueError:
                    flash('Invalid density value', 'error')
                    return redirect(url_for('developer.create_global_item'))

            capacity = request.form.get('capacity')
            if capacity:
                try:
                    new_item.capacity = float(capacity)
                except ValueError:
                    flash('Invalid capacity value', 'error')
                    return redirect(url_for('developer.create_global_item'))

            new_item.capacity_unit = request.form.get('capacity_unit', '').strip() or None
            # Container attributes (optional)
            try:
                new_item.container_material = (request.form.get('container_material') or '').strip() or None
                new_item.container_type = (request.form.get('container_type') or '').strip() or None
                new_item.container_style = (request.form.get('container_style') or '').strip() or None
                new_item.container_color = (request.form.get('container_color') or '').strip() or None
            except Exception:
                pass
            new_item.default_is_perishable = request.form.get('default_is_perishable') == 'on'

            shelf_life = request.form.get('recommended_shelf_life_days')
            if shelf_life:
                try:
                    new_item.recommended_shelf_life_days = int(shelf_life)
                except ValueError:
                    flash('Invalid shelf life value', 'error')
                    return redirect(url_for('developer.create_global_item'))

            # Handle aka_names (comma-separated)
            aka_names = request.form.get('aka_names', '').strip()
            if aka_names:
                new_item.aka_names = [n.strip() for n in aka_names.split(',') if n.strip()]

            db.session.add(new_item)
            db.session.commit()

            # Emit event
            try:
                from app.services.event_emitter import EventEmitter
                from flask_login import current_user
                # Resolve category name for telemetry
                category_name = None
                if ingredient_category_id:
                    from app.models.category import IngredientCategory
                    cat_obj = IngredientCategory.query.get(ingredient_category_id)
                    category_name = cat_obj.name if cat_obj else None
                EventEmitter.emit(
                    event_name='global_item_created',
                    properties={
                        'name': name,
                        'item_type': item_type,
                        'ingredient_category': category_name
                    },
                    user_id=getattr(current_user, 'id', None),
                    entity_type='global_item',
                    entity_id=new_item.id
                )
            except Exception:
                pass

            flash(f'Global item "{name}" created successfully', 'success')
            return redirect(url_for('developer.global_item_detail', item_id=new_item.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating global item: {str(e)}', 'error')
            return redirect(url_for('developer.create_global_item'))

    # GET request - show form
    # Get available global ingredient categories from IngredientCategory table
    from app.models.category import IngredientCategory
    global_ingredient_categories = IngredientCategory.query.filter_by(
        organization_id=None, 
        is_active=True,
        is_global_category=True
    ).order_by(IngredientCategory.name).all()

    return render_template('developer/create_global_item.html', global_ingredient_categories=global_ingredient_categories)

@developer_bp.route('/global-items/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_global_item(item_id):
    """Delete a global item, handling organization inventory disconnection"""
    try:
        data = request.get_json()
        confirm_name = data.get('confirm_name', '').strip()
        force_delete = data.get('force_delete', False)

        item = GlobalItem.query.get_or_404(item_id)

        # Validate confirmation
        if confirm_name != item.name:
            return jsonify({
                'success': False, 
                'error': f'Confirmation text must match exactly: "{item.name}"'
            })

        # Check for connected inventory items
        from app.models.inventory import InventoryItem
        connected_items = InventoryItem.query.filter_by(global_item_id=item.id).all()

        if connected_items and not force_delete:
            # Return info about connected items for user decision
            org_names = list(set([inv_item.organization.name for inv_item in connected_items if inv_item.organization]))
            return jsonify({
                'success': False,
                'requires_confirmation': True,
                'connected_count': len(connected_items),
                'organizations': org_names,
                'message': f'This global item is connected to {len(connected_items)} inventory items across {len(org_names)} organizations. These will be disconnected and become organization-owned items.'
            })

        # Proceed with deletion
        item_name = item.name
        connected_count = len(connected_items)

        # Default behavior: soft-delete (archive) the global item
        if not force_delete:
            from datetime import datetime
            item.is_archived = True
            item.archived_at = datetime.utcnow()
            item.archived_by = current_user.id
            db.session.commit()
        else:
            # Hard delete: Disconnect all inventory items (set global_item_id to NULL and ownership='org')
            for inv_item in connected_items:
                inv_item.global_item_id = None
                try:
                    inv_item.ownership = 'org'
                except Exception:
                    pass
            # Delete the global item
            db.session.delete(item)
            db.session.commit()

        # Log the deletion for audit purposes
        import logging
        logging.warning(f"GLOBAL_ITEM_DELETED: Developer {current_user.username} deleted global item '{item_name}' (ID: {item_id}). {connected_count} inventory items disconnected and converted to organization-owned.")

        # Emit event
        try:
            from app.services.event_emitter import EventEmitter
            EventEmitter.emit(
                event_name='global_item_deleted' if force_delete else 'global_item_archived',
                properties={'name': item_name, 'connected_count': connected_count},
                user_id=getattr(current_user, 'id', None),
                entity_type='global_item',
                entity_id=item_id
            )
        except Exception:
            pass

        if not force_delete:
            return jsonify({
                'success': True,
                'message': f'Global item "{item_name}" archived successfully.'
            })
        else:
            return jsonify({
                'success': True,
                'message': f'Global item "{item_name}" deleted successfully. {connected_count} connected inventory items converted to organization-owned items.'
            })

    except Exception as e:
        db.session.rollback()
        import logging
        logging.error(f"GLOBAL_ITEM_DELETE_FAILED: Error deleting global item {item_id}: {str(e)}")
        return jsonify({
            'success': False, 
            'error': f'Failed to delete global item: {str(e)}'
        })

@developer_bp.route('/inventory-analytics')
@login_required
def inventory_analytics_stub():
    """Developer inventory analytics (feature-flagged)."""
    from flask import current_app
    enabled = current_app.config.get('FEATURE_INVENTORY_ANALYTICS', False)
    if not enabled:
        flash('Inventory analytics is not enabled for this environment.', 'info')
        return redirect(url_for('developer.dashboard'))
    return render_template('developer/inventory_analytics.html')


# ===================== Integrations & Launch Checklist =====================

@developer_bp.route('/integrations')
@login_required
def integrations_checklist():
    """Comprehensive integrations and launch checklist (developer only)."""
    from flask import current_app
    from app.services.email_service import EmailService
    from app.services.stripe_service import StripeService
    from app.models.subscription_tier import SubscriptionTier

    # Email provider status
    email_provider = (current_app.config.get('EMAIL_PROVIDER') or 'smtp').lower()
    email_configured = EmailService.is_configured()
    email_keys = {
        'SMTP': bool(current_app.config.get('MAIL_SERVER')),
        'SendGrid': bool(current_app.config.get('SENDGRID_API_KEY')),
        'Postmark': bool(current_app.config.get('POSTMARK_SERVER_TOKEN')),
        'Mailgun': bool(current_app.config.get('MAILGUN_API_KEY') and current_app.config.get('MAILGUN_DOMAIN')),
    }

    # Stripe status
    stripe_secret = current_app.config.get('STRIPE_SECRET_KEY')
    stripe_webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
    tiers_count = SubscriptionTier.query.count()
    stripe_status = {
        'secret_key_present': bool(stripe_secret),
        'webhook_secret_present': bool(stripe_webhook_secret),
        'tiers_configured': tiers_count > 0,
    }

    # Feature flags
    feature_flags = {
        'FEATURE_INVENTORY_ANALYTICS': bool(current_app.config.get('FEATURE_INVENTORY_ANALYTICS', False)),
        'TOOLS_SOAP': bool(current_app.config.get('TOOLS_SOAP', True)),
        'TOOLS_CANDLES': bool(current_app.config.get('TOOLS_CANDLES', True)),
        'TOOLS_LOTIONS': bool(current_app.config.get('TOOLS_LOTIONS', True)),
        'TOOLS_HERBAL': bool(current_app.config.get('TOOLS_HERBAL', True)),
        'TOOLS_BAKING': bool(current_app.config.get('TOOLS_BAKING', True)),
    }

    # Logging/PII
    logging_status = {
        'LOG_LEVEL': current_app.config.get('LOG_LEVEL', 'INFO'),
        'LOG_REDACT_PII': current_app.config.get('LOG_REDACT_PII', True),
    }

    # POS/Shopify (stub)
    shopify_status = {
        'status': 'stubbed',
        'notes': 'POS/Shopify integration is stubbed. Enable later via a dedicated adapter.'
    }

    return render_template(
        'developer/integrations.html',
        email_provider=email_provider,
        email_configured=email_configured,
        email_keys=email_keys,
        stripe_status=stripe_status,
        tiers_count=tiers_count,
        feature_flags=feature_flags,
        logging_status=logging_status,
        shopify_status=shopify_status
    )


@developer_bp.route('/integrations/test-email', methods=['POST'])
@login_required
def integrations_test_email():
    """Send a test email to current user's email if configured."""
    try:
        from app.services.email_service import EmailService
        if not EmailService.is_configured():
            return jsonify({'success': False, 'error': 'Email is not configured'}), 400
        recipient = getattr(current_user, 'email', None)
        if not recipient:
            return jsonify({'success': False, 'error': 'Current user has no email address'}), 400
        subject = 'BatchTrack Test Email'
        html_body = '<p>This is a test email from BatchTrack Integrations Checklist.</p>'
        ok = EmailService._send_email(recipient, subject, html_body, 'This is a test email from BatchTrack Integrations Checklist.')
        if ok:
            return jsonify({'success': True, 'message': f'Test email sent to {recipient}'})
        return jsonify({'success': False, 'error': 'Failed to send email'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@developer_bp.route('/integrations/test-stripe', methods=['POST'])
@login_required
def integrations_test_stripe():
    """Test Stripe connectivity (no secrets shown)."""
    try:
        from app.services.stripe_service import StripeService
        ok = StripeService.initialize_stripe()
        if not ok:
            return jsonify({'success': False, 'error': 'Stripe secret not configured'}), 400
        # Try a harmless list call
        import stripe
        try:
            prices = stripe.Price.list(limit=1)
            return jsonify({'success': True, 'message': f"Stripe reachable. Prices found: {len(prices.data)}"})
        except Exception as e:
            return jsonify({'success': False, 'error': f"Stripe API error: {e}"}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@developer_bp.route('/integrations/stripe-events', methods=['GET'])
@login_required
def integrations_stripe_events():
    """Summarize recent Stripe webhook events from the database."""
    try:
        from app.models.stripe_event import StripeEvent
        total = StripeEvent.query.count()
        last = StripeEvent.query.order_by(StripeEvent.id.desc()).first()
        payload = {'total_events': total}
        if last:
            payload.update({
                'last_event_id': last.event_id,
                'last_event_type': last.event_type,
                'last_status': last.status,
                'last_processed_at': getattr(last, 'processed_at', None).isoformat() if getattr(last, 'processed_at', None) else None
            })
        return jsonify({'success': True, 'data': payload})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@developer_bp.route('/integrations/feature-flags', methods=['POST'])
@login_required
def integrations_set_feature_flags():
    """Set feature flags (developer only; stored in-app and persisted to settings.json)."""
    try:
        from flask import current_app
        if current_user.user_type != 'developer':
            return jsonify({'success': False, 'error': 'Developer access required'}), 403
        data = request.get_json() or {}
        
        # Define allowed flags
        allowed_flags = [
            # Core business features
            'FEATURE_FIFO_TRACKING',
            'FEATURE_BARCODE_SCANNING',
            'FEATURE_PRODUCT_VARIANTS',
            'FEATURE_AUTO_SKU_GENERATION',
            'FEATURE_RECIPE_VARIATIONS',
            'FEATURE_COST_TRACKING',
            'FEATURE_EXPIRATION_TRACKING',
            'FEATURE_BULK_OPERATIONS',
            
            # Developer & advanced features
            'FEATURE_INVENTORY_ANALYTICS',
            'FEATURE_DEBUG_MODE',
            'FEATURE_AUTO_BACKUP',
            'FEATURE_CSV_EXPORT',
            'FEATURE_ADVANCED_REPORTS',
            'FEATURE_GLOBAL_ITEM_LIBRARY',
            
            # Notification systems
            'FEATURE_EMAIL_NOTIFICATIONS',
            'FEATURE_BROWSER_NOTIFICATIONS',
            
            # Integration features
            'FEATURE_SHOPIFY_INTEGRATION',
            'FEATURE_API_ACCESS',
            'FEATURE_OAUTH_PROVIDERS',
            
            # AI features
            'FEATURE_AI_RECIPE_OPTIMIZATION',
            'FEATURE_AI_DEMAND_FORECASTING',
            'FEATURE_AI_QUALITY_INSIGHTS',
            
            # Public tools
            'TOOLS_SOAP',
            'TOOLS_CANDLES', 
            'TOOLS_LOTIONS',
            'TOOLS_HERBAL',
            'TOOLS_BAKING'
        ]
        
        # Update app config for allowed flags
        for flag in allowed_flags:
            if flag in data:
                value = bool(data[flag])
                current_app.config[flag] = value
        
        # Persist to settings.json for next boot
        try:
            import json, os
            settings = {}
            if os.path.exists('settings.json'):
                with open('settings.json', 'r') as f:
                    settings = json.load(f) or {}
            
            ff = settings.get('feature_flags', {}) or {}
            for flag in allowed_flags:
                if flag in data:
                    ff[flag] = bool(data[flag])
                    
            settings['feature_flags'] = ff
            with open('settings.json', 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception:
            pass
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@developer_bp.route('/integrations/check-webhook', methods=['GET'])
@login_required
def integrations_check_webhook():
    """Verify webhook endpoint HTTP reachability (does not validate Stripe signature)."""
    try:
        from flask import current_app
        import requests
        base = request.host_url.rstrip('/')
        # Use our known webhook path
        url = f"{base}/billing/webhooks/stripe"
        # Send a harmless GET to see if the route 405s (expected) or 404s
        try:
            resp = requests.get(url, timeout=5)
            status = resp.status_code
            message = 'reachable (method not allowed expected)' if status == 405 else f'response {status}'
            return jsonify({'success': True, 'url': url, 'status': status, 'message': message})
        except Exception as e:
            return jsonify({'success': False, 'url': url, 'error': f'Connection error: {e}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@developer_bp.route('/analytics-catalog')
@login_required
def analytics_catalog():
    """Developer catalog of analytics data points and domains."""
    domains = [
        {
            'name': 'Inventory',
            'description': 'Movements, spoilage, waste, usage, value held',
            'sources': ['UnifiedInventoryHistory', 'InventoryLot', 'InventoryItem', 'FreshnessSnapshot', 'domain_event: inventory_adjusted'],
            'events': ['inventory_adjusted'],
            'data_points': [
                'Quantity delta by change_type (restock, batch, use, spoil, expired, damaged, trash, recount, returned, refunded, release_reservation)',
                'Unit and normalized unit conversions',
                'Cost impact per movement (when provided)',
                'Freshness: avg days-to-usage, avg days-to-spoilage, freshness efficiency score',
                'Total cost held (derived, warehouse-level)',
                'Spoilage rate and waste rate (derived from movements)'
            ]
        },
        {
            'name': 'Batches',
            'description': 'Lifecycle, efficiency, costs, yield',
            'sources': ['Batch', 'BatchIngredient', 'BatchContainer', 'Extra*', 'BatchStats', 'domain_event: batch_started|batch_completed|batch_cancelled'],
            'events': ['batch_started', 'batch_completed', 'batch_cancelled'],
            'data_points': [
                'Planned vs actual fill efficiency (containment efficiency)',
                'Yield variance %',
                'Cost variance % (planned vs actual)',
                'Total planned/actual cost',
                'Batch duration (minutes)',
                'Status (completed, failed, cancelled)'
            ]
        },
        {
            'name': 'Products & SKUs',
            'description': 'On-hand, reservations, sales, unit costs',
            'sources': ['Product', 'ProductVariant', 'ProductSKU', 'InventoryItem (type=product)'],
            'events': ['product_created', 'product_variant_created', 'sku_created'],
            'data_points': [
                'On-hand quantity by SKU',
                'Unit cost (when available)',
                'Low stock threshold status',
                'Reservations/sales velocity (when integrated)'
            ]
        },
        {
            'name': 'Recipes',
            'description': 'Success rates, averages, cost baselines',
            'sources': ['Recipe', 'RecipeIngredient', 'RecipeStats'],
            'events': ['recipe_created', 'recipe_updated', 'recipe_deleted'],
            'data_points': [
                'Total/completed/failed batches per recipe',
                'Average fill efficiency, yield variance, cost variance',
                'Average cost per batch, per unit',
                'Success rate %'
            ]
        },
        {
            'name': 'Timers',
            'description': 'Task durations for batches/tasks',
            'sources': ['BatchTimer'],
            'events': ['timer_started', 'timer_stopped'],
            'data_points': [
                'Timer durations (seconds)',
                'Active, expired, completed timers',
                'Per-batch timing aggregates (p50/p90 to compute in warehouse)'
            ]
        },
        {
            'name': 'Global Item Library',
            'description': 'Canonical items, adoption across orgs',
            'sources': ['GlobalItem'],
            'events': ['global_item_created', 'global_item_archived', 'global_item_deleted'],
            'data_points': [
                'Adoption across organizations (count of org-linked items)',
                'Data quality: missing density/capacity/shelf-life'
            ]
        },
        {
            'name': 'Organizations & Users',
            'description': 'Tenancy, active users, tiers',
            'sources': ['Organization', 'User', 'OrganizationStats', 'UserStats'],
            'events': [],
            'data_points': [
                'Org totals: batches, completed/failed/cancelled',
                'Users: total and active',
                'Inventory: total items and total value',
                'Products: total products, total made'
            ]
        }
    ]

    return render_template('developer/analytics_catalog.html', domains=domains)


# ProductCategory management
@developer_bp.route('/product-categories')
@login_required
def product_categories():
    categories = ProductCategory.query.order_by(ProductCategory.name.asc()).all()
    return render_template('developer/categories/list.html', categories=categories)


@developer_bp.route('/product-categories/new', methods=['GET', 'POST'])
@login_required
def create_product_category():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        is_typically_portioned = True if request.form.get('is_typically_portioned') == 'on' else False
        sku_name_template = (request.form.get('sku_name_template') or '').strip() or None
        if not name:
            flash('Name is required', 'error')
            return redirect(url_for('developer.create_product_category'))
        exists = ProductCategory.query.filter(ProductCategory.name.ilike(name)).first()
        if exists:
            flash('Category name already exists', 'error')
            return redirect(url_for('developer.create_product_category'))
        cat = ProductCategory(name=name, is_typically_portioned=is_typically_portioned, sku_name_template=sku_name_template)
        from app.extensions import db
        db.session.add(cat)
        db.session.commit()
        flash('Product category created', 'success')
        return redirect(url_for('developer.product_categories'))
    return render_template('developer/categories/new.html')


@developer_bp.route('/product-categories/<int:cat_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product_category(cat_id):
    cat = ProductCategory.query.get_or_404(cat_id)
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        is_typically_portioned = True if request.form.get('is_typically_portioned') == 'on' else False
        sku_name_template = (request.form.get('sku_name_template') or '').strip() or None
        if not name:
            flash('Name is required', 'error')
            return redirect(url_for('developer.edit_product_category', cat_id=cat_id))
        conflict = ProductCategory.query.filter(ProductCategory.id != cat_id).filter(ProductCategory.name.ilike(name)).first()
        if conflict:
            flash('Another category with that name exists', 'error')
            return redirect(url_for('developer.edit_product_category', cat_id=cat_id))
        cat.name = name
        cat.is_typically_portioned = is_typically_portioned
        cat.sku_name_template = sku_name_template
        from app.extensions import db
        db.session.commit()
        flash('Product category updated', 'success')
        return redirect(url_for('developer.product_categories'))
    return render_template('developer/categories/edit.html', category=cat)


@developer_bp.route('/product-categories/<int:cat_id>/delete', methods=['POST'])
@login_required
def delete_product_category(cat_id):
    from app.extensions import db
    cat = ProductCategory.query.get_or_404(cat_id)
    # Prevent delete if in use
    from app.models.product import Product
    from app.models.recipe import Recipe
    in_use = db.session.query(Product).filter_by(category_id=cat.id).first() or db.session.query(Recipe).filter_by(category_id=cat.id).first()
    if in_use:
        flash('Cannot delete category that is used by products or recipes', 'error')
        return redirect(url_for('developer.product_categories'))
    db.session.delete(cat)
    db.session.commit()
    flash('Product category deleted', 'success')
    return redirect(url_for('developer.product_categories'))

@developer_bp.route('/waitlist-statistics')
@require_developer_permission('system_admin')
def waitlist_statistics():
    """View waitlist statistics and data"""
    import json
    import os
    from datetime import datetime

    waitlist_file = 'data/waitlist.json'
    waitlist_data = []

    if os.path.exists(waitlist_file):
        try:
            with open(waitlist_file, 'r') as f:
                waitlist_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            waitlist_data = []

    # Process data for display
    processed_data = []
    for entry in waitlist_data:
        # Format timestamp
        timestamp = entry.get('timestamp', '')
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                formatted_date = dt.strftime('%Y-%m-%d %H:%M UTC')
            except:
                formatted_date = timestamp
        else:
            formatted_date = 'Unknown'

        # Build full name
        first_name = entry.get('first_name', '')
        last_name = entry.get('last_name', '')
        name = entry.get('name', '')  # Legacy field

        if first_name or last_name:
            full_name = f"{first_name} {last_name}".strip()
        elif name:
            full_name = name
        else:
            full_name = 'Not provided'

        processed_data.append({
            'email': entry.get('email', ''),
            'full_name': full_name,
            'business_type': entry.get('business_type', 'Not specified'),
            'formatted_date': formatted_date,
            'source': entry.get('source', 'Unknown')
        })

    # Sort by most recent first
    processed_data.sort(key=lambda x: x.get('formatted_date', ''), reverse=True)

    return render_template('developer/waitlist_statistics.html', 
                         waitlist_data=processed_data,
                         total_signups=len(waitlist_data))

# Customer support filtering routes
@developer_bp.route('/select-org/<int:org_id>')
@login_required
def select_organization(org_id):
    """Select an organization to view as developer (customer support)"""
    org = Organization.query.get_or_404(org_id)
    session['dev_selected_org_id'] = org_id
    flash(f'Now viewing data for: {org.name} (Customer Support Mode)', 'info')
    return redirect(url_for('app_routes.dashboard'))



# Modified routes for developer masquerading
@developer_bp.route('/view-as-organization/<int:org_id>')
@login_required
@permission_required('dev.system_admin')
def view_as_organization(org_id):
    """Set session to view as a specific organization (customer support)"""
    organization = Organization.query.get_or_404(org_id)

    # Clear any existing masquerade data first
    session.pop('dev_selected_org_id', None)
    session.pop('dev_masquerade_context', None)

    # Store in session for middleware to use
    session['dev_selected_org_id'] = org_id
    session['dev_masquerade_context'] = {
        'org_name': organization.name,
        'started_at': TimezoneUtils.utc_now().isoformat()
    }
    session.permanent = True

    flash(f'Now viewing as organization: {organization.name}. Landing on user dashboard.', 'info')
    return redirect(url_for('app_routes.dashboard'))  # Land on user dashboard, not org dashboard

@developer_bp.route('/clear-organization-filter')
@login_required
@permission_required('dev.system_admin')
def clear_organization_filter():
    """Clear the organization filter and return to developer view"""
    org_name = None
    if 'dev_selected_org_id' in session:
        org_id = session['dev_selected_org_id']
        org = Organization.query.get(org_id)
        org_name = org.name if org else 'Unknown'

    # Clear all masquerade-related session data
    session.pop('dev_selected_org_id', None)
    session.pop('dev_masquerade_context', None)

    # Also clear any organization-scoped data that might be cached
    session.pop('dismissed_alerts', None)  # Clear dismissed alerts from customer view

    message = f'Cleared organization filter and session data'
    if org_name:
        message += f' (was viewing: {org_name})'

    flash(message, 'info')
    return redirect(url_for('developer.dashboard'))


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

@developer_bp.route('/reference-categories/get-visibility', methods=['GET'])
@login_required
def get_category_visibility():
    """Get visibility settings for a category"""
    try:
        category_name = request.args.get('category', '').strip()

        if not category_name:
            return jsonify({'success': False, 'error': 'Category name is required'})

        # Find the category
        from app.models.category import IngredientCategory
        category = IngredientCategory.query.filter_by(
            name=category_name,
            organization_id=None,
            is_global_category=True
        ).first()

        if not category:
            return jsonify({'success': False, 'error': 'Category not found'})

        visibility = {
            'show_saponification_value': getattr(category, 'show_saponification_value', False),
            'show_iodine_value': getattr(category, 'show_iodine_value', False),
            'show_melting_point': getattr(category, 'show_melting_point', False),
            'show_flash_point': getattr(category, 'show_flash_point', False),
            'show_ph_value': getattr(category, 'show_ph_value', False),
            'show_moisture_content': getattr(category, 'show_moisture_content', False),
            'show_shelf_life_months': getattr(category, 'show_shelf_life_months', False),
            'show_comedogenic_rating': getattr(category, 'show_comedogenic_rating', False)
        }

        return jsonify({'success': True, 'visibility': visibility})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/reference-categories/update-visibility', methods=['POST'])
@login_required
def update_category_visibility():
    """Update visibility settings for a category"""
    try:
        data = request.get_json()
        category_name = data.get('category', '').strip()

        if not category_name:
            return jsonify({'success': False, 'error': 'Category name is required'})

        # Find the category
        from app.models.category import IngredientCategory
        category = IngredientCategory.query.filter_by(
            name=category_name,
            organization_id=None,
            is_global_category=True
        ).first()

        if not category:
            return jsonify({'success': False, 'error': 'Category not found'})

        # Update visibility settings
        category.show_saponification_value = data.get('show_saponification_value', False)
        category.show_iodine_value = data.get('show_iodine_value', False)
        category.show_melting_point = data.get('show_melting_point', False)
        category.show_flash_point = data.get('show_flash_point', False)
        category.show_ph_value = data.get('show_ph_value', False)
        category.show_moisture_content = data.get('show_moisture_content', False)
        category.show_shelf_life_months = data.get('show_shelf_life_months', False)
        category.show_comedogenic_rating = data.get('show_comedogenic_rating', False)

        db.session.commit()

        return jsonify({
            'success': True, 
            'message': f'Visibility settings updated for category "{category_name}"'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})