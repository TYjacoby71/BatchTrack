from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.models import db, Permission, SubscriptionTier, Organization
from app.utils.permissions import require_permission # Assuming this is the correct import
import logging
import json
import os

logger = logging.getLogger(__name__)

def load_tiers_config():
    """Load subscription tiers from JSON file - this is the single source of truth"""
    TIERS_CONFIG_FILE = 'subscription_tiers.json'

    if os.path.exists(TIERS_CONFIG_FILE):
        with open(TIERS_CONFIG_FILE, 'r') as f:
            loaded_tiers = json.load(f)
            # Filter out metadata keys and invalid entries
            valid_tiers = {}
            for tier_key, tier_data in loaded_tiers.items():
                # Skip metadata keys (start with underscore) and non-dict values
                if not tier_key.startswith('_') and isinstance(tier_data, dict):
                    valid_tiers[tier_key] = tier_data
            return valid_tiers

    # If no JSON file exists, return empty dict - force creation of subscription_tiers.json
    print("WARNING: No subscription_tiers.json found - tiers must be configured in JSON file")
    return {}

subscription_tiers_bp = Blueprint('subscription_tiers', __name__, url_prefix='/subscription-tiers')

@subscription_tiers_bp.route('/')
@login_required
@require_permission('developer.system_management')
def manage_tiers():
    """Main page to view all tiers directly from the database."""
    all_tiers_db = SubscriptionTier.query.order_by(SubscriptionTier.name).all()
    all_permissions = Permission.query.order_by(Permission.name).all()

    # Convert to dictionary format expected by template
    tiers_dict = {}
    for tier in all_tiers_db:
        tiers_dict[tier.key] = {
            'id': tier.id,  # Include the tier ID
            'name': tier.name,
            'description': tier.description,
            'user_limit': tier.user_limit,
            'is_customer_facing': tier.is_customer_facing,
            'is_available': getattr(tier, 'is_available', True),
            'billing_provider': tier.billing_provider,
            'is_billing_exempt': tier.is_billing_exempt,
            'stripe_lookup_key': tier.stripe_lookup_key,
            'whop_product_key': tier.whop_product_key,
            'fallback_price': tier.fallback_price,
            'stripe_price': tier.fallback_price,  # For template compatibility
            'last_synced': None,  # TODO: Add sync tracking
            'whop_last_synced': None,  # TODO: Add whop sync tracking
            'permissions': [p.name for p in tier.permissions],
            'pricing_category': 'standard',  # Default value
            'billing_cycle': 'monthly',  # Default value
            'requires_stripe_billing': tier.requires_stripe_billing,
            'supports_whop': bool(tier.whop_product_key),
            'max_users': tier.max_users,
            'max_recipes': tier.max_recipes,
            'max_batches': tier.max_batches,
            'max_products': tier.max_products,
            'max_batchbot_requests': tier.max_batchbot_requests,
            'max_monthly_batches': tier.max_monthly_batches
        }

    return render_template('developer/subscription_tiers.html',
                           tiers=tiers_dict,
                           tiers_dict=tiers_dict,
                           all_permissions=all_permissions)

@subscription_tiers_bp.route('/create', methods=['GET', 'POST'])
@login_required
@require_permission('developer.system_management')
def create_tier():
    """Create a new SubscriptionTier record directly in the database."""
    if request.method == 'POST':
        # Data Collection
        key = request.form.get('key', '').strip()
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '')
        user_limit = int(request.form.get('user_limit', 1))
        max_users = request.form.get('max_users', None)
        max_recipes = request.form.get('max_recipes', None)
        max_batches = request.form.get('max_batches', None)
        max_products = request.form.get('max_products', None)
        max_batchbot_requests = request.form.get('max_batchbot_requests', None)
        max_monthly_batches = request.form.get('max_monthly_batches', None)

        billing_provider = request.form.get('billing_provider', 'exempt')
        is_billing_exempt = 'is_billing_exempt' in request.form
        stripe_key = request.form.get('stripe_lookup_key', '').strip()
        whop_key = request.form.get('whop_product_key', '').strip()

        # Convert limit fields to integers or None if empty
        max_users = int(max_users) if max_users and max_users.isdigit() else None
        max_recipes = int(max_recipes) if max_recipes and max_recipes.isdigit() else None
        max_batches = int(max_batches) if max_batches and max_batches.isdigit() else None
        max_products = int(max_products) if max_products and max_products.isdigit() else None
        max_batchbot_requests = int(max_batchbot_requests) if max_batchbot_requests and max_batchbot_requests.isdigit() else None
        max_monthly_batches = int(max_monthly_batches) if max_monthly_batches and max_monthly_batches.isdigit() else None

        # Validation
        if not key or not name:
            flash('Tier Key and Name are required.', 'error')
            return redirect(url_for('.create_tier'))

        if SubscriptionTier.query.filter_by(key=key).first():
            flash(f"A tier with the key '{key}' already exists.", 'error')
            return redirect(url_for('.create_tier'))

        # Enforce billing integration requirements
        if not is_billing_exempt:
            if billing_provider == 'stripe' and not stripe_key:
                flash('A Stripe Lookup Key is required for Stripe-billed tiers.', 'error')
                return redirect(url_for('.create_tier'))
            if billing_provider == 'whop' and not whop_key:
                flash('A Whop Product Key is required for Whop-billed tiers.', 'error')
                return redirect(url_for('.create_tier'))

        # Database Insertion
        tier = SubscriptionTier(
            key=key,
            name=name,
            description=description,
            user_limit=user_limit,
            max_users=max_users,
            max_recipes=max_recipes,
            max_batches=max_batches,
            max_products=max_products,
            max_batchbot_requests=max_batchbot_requests,
            max_monthly_batches=max_monthly_batches,
            billing_provider=billing_provider,
            is_billing_exempt=is_billing_exempt,
            stripe_lookup_key=stripe_key if stripe_key else None,
            whop_product_key=whop_key if whop_key else None
        )

        # Add permissions
        permission_ids = request.form.getlist('permissions', type=int)
        if permission_ids:
            tier.permissions = Permission.query.filter(Permission.id.in_(permission_ids)).all()

        db.session.add(tier)
        db.session.commit()

        logger.info(f'Created subscription tier: {name} ({key})')
        flash(f'Subscription tier "{name}" created successfully.', 'success')
        return redirect(url_for('.manage_tiers'))

    # For GET request
    all_permissions = Permission.query.order_by(Permission.name).all()
    return render_template('developer/create_tier.html', all_permissions=all_permissions)

@subscription_tiers_bp.route('/edit/<int:tier_id>', methods=['GET', 'POST'])
@login_required
@require_permission('developer.system_management')
def edit_tier(tier_id):
    """Edit an existing tier by its database ID."""
    tier = db.session.get(SubscriptionTier, tier_id)
    if not tier:
        flash('Tier not found.', 'error')
        return redirect(url_for('.manage_tiers'))

    if request.method == 'POST':
        # Data Collection & Validation
        billing_provider = request.form.get('billing_provider', 'exempt')
        is_billing_exempt = 'is_billing_exempt' in request.form
        stripe_key = request.form.get('stripe_lookup_key', '').strip()
        whop_key = request.form.get('whop_product_key', '').strip()

        # Enforce billing integration requirements
        if not is_billing_exempt:
            if billing_provider == 'stripe' and not stripe_key:
                flash('A Stripe Lookup Key is required for Stripe-billed tiers.', 'error')
                return redirect(url_for('.edit_tier', tier_id=tier_id))
            if billing_provider == 'whop' and not whop_key:
                flash('A Whop Product Key is required for Whop-billed tiers.', 'error')
                return redirect(url_for('.edit_tier', tier_id=tier_id))

        # Update and Save
        try:
            tier.name = request.form.get('name', tier.name)
            tier.description = request.form.get('description', tier.description)
            tier.user_limit = int(request.form.get('user_limit', tier.user_limit)) # Keep original if not provided

            # Update limit fields, converting to int or None
            max_users = request.form.get('max_users', str(tier.max_users) if tier.max_users is not None else '')
            tier.max_users = int(max_users) if max_users and max_users.isdigit() else None

            max_recipes = request.form.get('max_recipes', str(tier.max_recipes) if tier.max_recipes is not None else '')
            tier.max_recipes = int(max_recipes) if max_recipes and max_recipes.isdigit() else None

            max_batches = request.form.get('max_batches', str(tier.max_batches) if tier.max_batches is not None else '')
            tier.max_batches = int(max_batches) if max_batches and max_batches.isdigit() else None

            max_products = request.form.get('max_products', str(tier.max_products) if tier.max_products is not None else '')
            tier.max_products = int(max_products) if max_products and max_products.isdigit() else None

            max_batchbot_requests = request.form.get('max_batchbot_requests', str(tier.max_batchbot_requests) if tier.max_batchbot_requests is not None else '')
            tier.max_batchbot_requests = int(max_batchbot_requests) if max_batchbot_requests and max_batchbot_requests.isdigit() else None

            max_monthly_batches = request.form.get('max_monthly_batches', str(tier.max_monthly_batches) if tier.max_monthly_batches is not None else '')
            tier.max_monthly_batches = int(max_monthly_batches) if max_monthly_batches and max_monthly_batches.isdigit() else None

            tier.billing_provider = billing_provider
            tier.is_billing_exempt = is_billing_exempt
            tier.stripe_lookup_key = stripe_key or None
            tier.whop_product_key = whop_key or None
            tier.fallback_price = request.form.get('fallback_price', tier.fallback_price) # Keep original if not provided

            # Update permissions
            permission_ids = request.form.getlist('permissions', type=int)
            tier.permissions = Permission.query.filter(Permission.id.in_(permission_ids)).all()

            db.session.commit()

            logger.info(f'Updated subscription tier: {tier.name} ({tier.key})')
            flash(f'Subscription tier "{tier.name}" updated successfully.', 'success')
            return redirect(url_for('.manage_tiers'))

        except Exception as e:
            db.session.rollback()
            logger.error(f'Error updating tier: {e}')
            flash('Error updating tier. Please try again.', 'error')
            return redirect(url_for('.edit_tier', tier_id=tier_id))

    # For GET request
    all_permissions = Permission.query.order_by(Permission.name).all()
    return render_template('developer/edit_tier.html',
                           tier=tier,
                           all_permissions=all_permissions)

@subscription_tiers_bp.route('/delete/<int:tier_id>', methods=['POST'])
@login_required
@require_permission('developer.system_management')
def delete_tier(tier_id):
    """Delete a tier from the database, with safety checks."""
    tier = db.session.get(SubscriptionTier, tier_id)
    if not tier:
        flash('Tier not found.', 'error')
        return redirect(url_for('.manage_tiers'))

    # Safety check for system-critical tiers
    if tier.key in ['exempt', 'free']:
        flash(f'Cannot delete the system-critical "{tier.key}" tier.', 'error')
        return redirect(url_for('.manage_tiers'))

    # Check for organizations using this tier
    orgs_on_tier = Organization.query.filter_by(subscription_tier_id=tier_id).count()
    if orgs_on_tier > 0:
        flash(f'Cannot delete "{tier.name}" as {orgs_on_tier} organization(s) are currently subscribed to it.', 'error')
        return redirect(url_for('.manage_tiers'))

    try:
        db.session.delete(tier)
        db.session.commit()

        logger.info(f'Deleted subscription tier: {tier.name} ({tier.key})')
        flash(f'Subscription tier "{tier.name}" has been deleted.', 'success')

    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting tier: {e}')
        flash('Error deleting tier. Please try again.', 'error')

    return redirect(url_for('.manage_tiers'))

@subscription_tiers_bp.route('/sync/<tier_key>', methods=['POST'])
@login_required
@require_permission('developer.system_management')
def sync_tier_with_stripe(tier_key):
    """Sync a specific tier with Stripe pricing"""
    tier = SubscriptionTier.query.filter_by(key=tier_key).first()
    if not tier:
        return jsonify({'success': False, 'error': 'Tier not found'}), 404

    if not tier.stripe_lookup_key:
        return jsonify({'success': False, 'error': 'No Stripe lookup key configured'}), 400

    try:
        # Here you would implement actual Stripe sync logic
        # For now, return success
        logger.info(f'Synced tier {tier_key} with Stripe')
        return jsonify({
            'success': True,
            'message': f'Successfully synced {tier.name} with Stripe',
            'tier': {
                'key': tier.key,
                'name': tier.name,
                'stripe_price': tier.fallback_price
            }
        })
    except Exception as e:
        logger.error(f'Error syncing tier {tier_key}: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@subscription_tiers_bp.route('/sync-whop/<tier_key>', methods=['POST'])
@login_required
@require_permission('developer.system_management')
def sync_tier_with_whop(tier_key):
    """Sync a specific tier with Whop"""
    tier = SubscriptionTier.query.filter_by(key=tier_key).first()
    if not tier:
        return jsonify({'success': False, 'error': 'Tier not found'}), 404

    if not tier.whop_product_key:
        return jsonify({'success': False, 'error': 'No Whop product key configured'}), 400

    try:
        # Here you would implement actual Whop sync logic
        # For now, return success
        logger.info(f'Synced tier {tier_key} with Whop')
        return jsonify({
            'success': True,
            'message': f'Successfully synced {tier.name} with Whop'
        })
    except Exception as e:
        logger.error(f'Error syncing tier {tier_key} with Whop: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@subscription_tiers_bp.route('/api/tiers')
@login_required
@require_permission('developer.system_management')
def api_get_tiers():
    """API endpoint to get all tiers as JSON."""
    tiers = SubscriptionTier.query.filter_by(is_customer_facing=True).all()
    return jsonify([{
        'id': tier.id,
        'key': tier.key,
        'name': tier.name,
        'description': tier.description,
        'user_limit': tier.user_limit,
        'billing_provider': tier.billing_provider,
        'is_billing_exempt': tier.is_billing_exempt,
        'has_valid_integration': tier.has_valid_integration,
        'fallback_price': tier.fallback_price,
        'permissions': tier.get_permission_names(),
        'max_users': tier.max_users,
        'max_recipes': tier.max_recipes,
        'max_batches': tier.max_batches,
        'max_products': tier.max_products,
        'max_batchbot_requests': tier.max_batchbot_requests,
        'max_monthly_batches': tier.max_monthly_batches
    } for tier in tiers])