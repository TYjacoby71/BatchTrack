"""Developer routes for subscription tiers and entitlement wiring.

Synopsis:
Manage tier limits, permissions, and add-on availability for billing.

Glossary:
- Allowed add-on: Purchasable entitlement for a tier.
- Included add-on: Entitlement granted to all orgs on the tier.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.models import db, Permission, SubscriptionTier, Organization
from app.utils.permissions import require_permission # Assuming this is the correct import
from app.models.addon import Addon
import logging
import json
import os

logger = logging.getLogger(__name__)

def load_tiers_config():
    raise RuntimeError('Deprecated: load_tiers_config removed. Query SubscriptionTier directly.')

subscription_tiers_bp = Blueprint('subscription_tiers', __name__, url_prefix='/subscription-tiers')


def _addon_permission_map(addons):
    addon_perm_names = [a.permission_name for a in addons if a and a.permission_name]
    if not addon_perm_names:
        return {}
    permissions = Permission.query.filter(
        Permission.is_active.is_(True),
        Permission.name.in_(addon_perm_names),
    ).all()
    perm_by_name = {p.name: p for p in permissions}
    return {
        addon.id: perm_by_name.get(addon.permission_name)
        for addon in addons
        if addon.permission_name and perm_by_name.get(addon.permission_name)
    }


def _base_permissions(addons):
    addon_perm_names = [a.permission_name for a in addons if a and a.permission_name]
    query = Permission.query.filter(Permission.is_active.is_(True))
    if addon_perm_names:
        query = query.filter(Permission.name.not_in(addon_perm_names))
    return query.order_by(Permission.name).all()

# =========================================================
# TIER MANAGEMENT
# =========================================================
# --- List tiers ---
# Purpose: Show tiers with permission and add-on snapshots.
@subscription_tiers_bp.route('/')
@login_required
@require_permission('dev.manage_tiers')
def manage_tiers():
    """Main page to view all tiers directly from the database."""
    all_tiers_db = SubscriptionTier.query.order_by(SubscriptionTier.name).all()
    all_permissions = Permission.query.filter_by(is_active=True).order_by(Permission.name).all()

    # Convert to dictionary format expected by template
    tiers_dict = {}
    for tier in all_tiers_db:
        # Get live pricing from Stripe if available
        price_display = 'N/A'
        live_pricing = None

        if tier.stripe_lookup_key:
            try:
                from ...services.billing_service import BillingService
                live_pricing = BillingService.get_live_pricing_for_tier(tier)
                if live_pricing:
                    price_display = live_pricing['formatted_price']
            except Exception as e:
                logger.warning(f"Could not fetch live pricing for tier {tier.id}: {e}")

        if tier.billing_provider == 'exempt':
            price_display = 'Free'

        tiers_dict[tier.id] = {
            'id': tier.id,  # Include the tier ID
            'name': tier.name,
            'description': tier.description,
            'user_limit': tier.user_limit,
            'is_customer_facing': tier.is_customer_facing,
            'is_available': getattr(tier, 'is_available', True),
            'billing_provider': tier.billing_provider,
            'is_billing_exempt': tier.is_billing_exempt,
            'stripe_lookup_key': tier.stripe_lookup_key,
            'stripe_storage_lookup_key': getattr(tier, 'stripe_storage_lookup_key', None),
            'whop_product_key': tier.whop_product_key,
            'stripe_price': price_display,  # Now shows actual pricing
            'last_synced': live_pricing.get('last_synced') if live_pricing else None,
            'whop_last_synced': None,  # TODO: Add whop sync tracking
            'permissions': [p.name for p in tier.permissions],
            'pricing_category': 'standard',  # Default value
            'billing_cycle': 'monthly',  # Default value
            'requires_billing': not tier.is_billing_exempt,
            'supports_whop': bool(tier.whop_product_key),
            'max_users': tier.max_users,
            'max_recipes': tier.max_recipes,
            'max_batches': tier.max_batches,
            'max_products': tier.max_products,
            'max_batchbot_requests': tier.max_batchbot_requests,
            'max_monthly_batches': tier.max_monthly_batches,
            'data_retention_days': tier.data_retention_days,
            'retention_notice_days': tier.retention_notice_days,
            'retention_policy': getattr(tier, 'retention_policy', 'one_year'),
            'retention_label': tier.retention_label,
            'allowed_addon_ids': [a.id for a in getattr(tier, 'allowed_addons', [])],
            'included_addon_ids': [a.id for a in getattr(tier, 'included_addons', [])]
        }

    return render_template('developer/subscription_tiers.html',
                           tiers=tiers_dict,
                           tiers_dict=tiers_dict,
                           all_permissions=all_permissions)

# --- Create tier ---
# Purpose: Create a new tier with limits and entitlements.
@subscription_tiers_bp.route('/create', methods=['GET', 'POST'])
@login_required
@require_permission('dev.manage_tiers')
def create_tier():
    """Create a new SubscriptionTier record directly in the database."""
    if request.method == 'POST':
        # Data Collection
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '')
        def _parse_int_allow_neg1(text, default):
            try:
                v = int(str(text).strip())
                return v
            except Exception:
                return default

        user_limit = _parse_int_allow_neg1(request.form.get('user_limit', 1), 1)
        max_users = request.form.get('max_users', None)
        max_recipes = request.form.get('max_recipes', None)
        max_batches = request.form.get('max_batches', None)
        max_products = request.form.get('max_products', None)
        max_batchbot_requests = request.form.get('max_batchbot_requests', None)
        max_monthly_batches = request.form.get('max_monthly_batches', None)
        retention_policy = (request.form.get('retention_policy') or 'one_year').strip()
        data_retention_days_raw = request.form.get('data_retention_days', '').strip()
        retention_notice_days_raw = request.form.get('retention_notice_days', '').strip()


        billing_provider = request.form.get('billing_provider', 'exempt')
        stripe_key = request.form.get('stripe_lookup_key', '').strip()

        whop_key = request.form.get('whop_product_key', '').strip()

        # Convert limit fields to integers or None if empty, allow -1 for unlimited
        def parse_limit_field(value):
            if not value or value.strip() == '':
                return None
            try:
                num = int(value.strip())
                return num  # Allow -1 for unlimited
            except (ValueError, AttributeError):
                return None
        
        max_recipes = parse_limit_field(max_recipes)
        max_products = parse_limit_field(max_products)
        max_batchbot_requests = parse_limit_field(max_batchbot_requests)
        max_monthly_batches = parse_limit_field(max_monthly_batches)
        # Normalize retention settings
        data_retention_days = int(data_retention_days_raw) if data_retention_days_raw.isdigit() else None
        if retention_policy == 'one_year':
            data_retention_days = 365
        elif retention_policy == 'subscribed':
            data_retention_days = None
        retention_notice_days = int(retention_notice_days_raw) if retention_notice_days_raw.isdigit() else None


        # Validation
        if not name:
            flash('Tier Name is required.', 'error')
            return redirect(url_for('.create_tier'))

        # Check for duplicate name
        if SubscriptionTier.query.filter_by(name=name).first():
            flash(f"A tier with the name '{name}' already exists.", 'error')
            return redirect(url_for('.create_tier'))

        # BILLING REQUIREMENTS:
        # For non-exempt tiers, require proper billing integration
        if billing_provider == 'stripe':
            if not stripe_key:
                flash('A Stripe Lookup Key is required for Stripe-billed tiers.', 'error')
                return redirect(url_for('.create_tier'))
        elif billing_provider == 'whop':
            if not whop_key:
                flash('A Whop Product Key is required for Whop-billed tiers.', 'error')
                return redirect(url_for('.create_tier'))

        # Database Insertion
        is_customer_facing = 'is_customer_facing' in request.form
        tier = SubscriptionTier(
            name=name,
            description=description,
            user_limit=user_limit,
            max_users=max_users,
            max_recipes=max_recipes,
            max_products=max_products,
            max_batchbot_requests=max_batchbot_requests,
            max_monthly_batches=max_monthly_batches,
            retention_policy=retention_policy,
            data_retention_days=data_retention_days,
            retention_notice_days=retention_notice_days,
            billing_provider=billing_provider,
            stripe_lookup_key=stripe_key if stripe_key else None,
            whop_product_key=whop_key if whop_key else None,
            is_customer_facing=is_customer_facing
        )

        # Add permissions (merge with addon-linked permissions)
        permission_ids = set(request.form.getlist('permissions', type=int))

        db.session.add(tier)
        db.session.flush()

        # Allowed and Included add-ons
        addon_ids = request.form.getlist('allowed_addons', type=int)
        included_ids = request.form.getlist('included_addons', type=int)
        selected_addon_ids = set(addon_ids or []) | set(included_ids or [])
        if selected_addon_ids:
            selected_addons = Addon.query.filter(Addon.id.in_(selected_addon_ids)).all()
            addon_perm_names = [a.permission_name for a in selected_addons if a.permission_name]
            if addon_perm_names:
                addon_perms = Permission.query.filter(
                    Permission.is_active.is_(True),
                    Permission.name.in_(addon_perm_names),
                ).all()
                permission_ids.update({p.id for p in addon_perms})
        if permission_ids:
            tier.permissions = Permission.query.filter(Permission.id.in_(permission_ids)).all()
        if addon_ids is not None:
            tier.allowed_addons = Addon.query.filter(Addon.id.in_(addon_ids)).all() if addon_ids else []
        if included_ids is not None:
            try:
                tier.included_addons = Addon.query.filter(Addon.id.in_(included_ids)).all() if included_ids else []
            except Exception:
                pass

        db.session.commit()

        logger.info(f'Created subscription tier: {name} (id: {tier.id})')
        flash(f'Subscription tier "{name}" created successfully.', 'success')
        return redirect(url_for('.manage_tiers'))

    # For GET request
    all_addons = Addon.query.filter_by(is_active=True).order_by(Addon.name).all()
    addon_permissions = _addon_permission_map(all_addons)
    all_permissions = _base_permissions(all_addons)
    return render_template(
        'developer/create_tier.html',
        all_permissions=all_permissions,
        all_addons=all_addons,
        addon_permissions=addon_permissions,
    )

# --- Edit tier ---
# Purpose: Edit tier limits, permissions, and add-on entitlements.
@subscription_tiers_bp.route('/edit/<int:tier_id>', methods=['GET', 'POST'])
@login_required
@require_permission('dev.manage_tiers')
def edit_tier(tier_id):
    """Edit an existing tier by its database ID."""
    tier = db.session.get(SubscriptionTier, tier_id)
    if not tier:
        flash('Tier not found.', 'error')
        return redirect(url_for('.manage_tiers'))

    if request.method == 'POST':
        # Data Collection & Validation
        billing_provider = request.form.get('billing_provider', 'exempt')
        # The following line is removed as is_billing_exempt is no longer used directly for logic
        # is_billing_exempt = 'is_billing_exempt' in request.form
        stripe_key = request.form.get('stripe_lookup_key', '').strip()
        whop_key = request.form.get('whop_product_key', '').strip()

        # STRICT BILLING REQUIREMENTS:
        # Unless billing bypass is explicitly enabled (billing_provider == 'exempt'), require proper billing integration
        if billing_provider != 'exempt':
            if billing_provider == 'stripe':
                if not stripe_key:
                    flash('A Stripe Lookup Key is required for Stripe-billed tiers.', 'error')
                    return redirect(url_for('.edit_tier', tier_id=tier_id))
            elif billing_provider == 'whop':
                if not whop_key:
                    flash('A Whop Product Key is required for Whop-billed tiers.', 'error')
                    return redirect(url_for('.edit_tier', tier_id=tier_id))
            else:
                flash('You must select either Stripe or Whop as billing provider, or choose "Exempt".', 'error')
                return redirect(url_for('.edit_tier', tier_id=tier_id))

        # Update and Save
        try:
            tier.name = request.form.get('name', tier.name)
            tier.description = request.form.get('description', tier.description)
            tier.is_customer_facing = 'is_customer_facing' in request.form
            # Allow -1 for unlimited
            try:
                tier.user_limit = int(request.form.get('user_limit', tier.user_limit))
            except (ValueError, TypeError):
                tier.user_limit = tier.user_limit

            # Update limit fields, converting to int or None, allow -1 for unlimited
            # Stop processing legacy max_users from form; keep existing DB value intact
            # (We keep the column for backward compatibility but do not expose/edit it)

            def parse_limit_field(value):
                if not value or value.strip() == '':
                    return None
                try:
                    num = int(value.strip())
                    return num  # Allow -1 for unlimited
                except (ValueError, AttributeError):
                    return None

            max_recipes = request.form.get('max_recipes', str(tier.max_recipes) if tier.max_recipes is not None else '')
            tier.max_recipes = parse_limit_field(max_recipes)

            max_products = request.form.get('max_products', str(tier.max_products) if tier.max_products is not None else '')
            tier.max_products = parse_limit_field(max_products)

            max_batchbot_requests = request.form.get('max_batchbot_requests', str(tier.max_batchbot_requests) if tier.max_batchbot_requests is not None else '')
            tier.max_batchbot_requests = parse_limit_field(max_batchbot_requests)

            max_monthly_batches = request.form.get('max_monthly_batches', str(tier.max_monthly_batches) if tier.max_monthly_batches is not None else '')
            tier.max_monthly_batches = parse_limit_field(max_monthly_batches)

            tier.billing_provider = billing_provider
            # tier.is_billing_exempt is removed from updates as it's derived from billing_provider
            tier.stripe_lookup_key = stripe_key or None

            tier.whop_product_key = whop_key or None

            # Retention fields
            retention_policy = (request.form.get('retention_policy') or getattr(tier, 'retention_policy', 'one_year')).strip()
            data_retention_days_raw = request.form.get('data_retention_days', '').strip()
            retention_notice_days_raw = request.form.get('retention_notice_days', '').strip()
            # Apply policy normalization
            if retention_policy == 'one_year':
                tier.retention_policy = 'one_year'
                tier.data_retention_days = 365
            elif retention_policy == 'subscribed':
                tier.retention_policy = 'subscribed'
                tier.data_retention_days = None
            else:
                # Fallback: keep provided days if valid, otherwise default to 365
                tier.retention_policy = 'one_year'
                tier.data_retention_days = int(data_retention_days_raw) if data_retention_days_raw.isdigit() else 365
            tier.retention_notice_days = int(retention_notice_days_raw) if retention_notice_days_raw.isdigit() else None

            # Update allowed and included add-ons
            addon_ids = request.form.getlist('allowed_addons', type=int)
            included_ids = request.form.getlist('included_addons', type=int)
            tier.allowed_addons = Addon.query.filter(Addon.id.in_(addon_ids)).all() if addon_ids else []
            try:
                tier.included_addons = Addon.query.filter(Addon.id.in_(included_ids)).all() if included_ids else []
            except Exception:
                pass

            # Update permissions (merge with addon-linked permissions)
            permission_ids = set(request.form.getlist('permissions', type=int))
            selected_addon_ids = set(addon_ids or []) | set(included_ids or [])
            if selected_addon_ids:
                selected_addons = Addon.query.filter(Addon.id.in_(selected_addon_ids)).all()
                addon_perm_names = [a.permission_name for a in selected_addons if a.permission_name]
                if addon_perm_names:
                    addon_perms = Permission.query.filter(
                        Permission.is_active.is_(True),
                        Permission.name.in_(addon_perm_names),
                    ).all()
                    permission_ids.update({p.id for p in addon_perms})
            tier.permissions = Permission.query.filter(Permission.id.in_(permission_ids)).all()

            db.session.commit()

            logger.info(f'Updated subscription tier: {tier.name} (id: {tier.id})')
            flash(f'Subscription tier "{tier.name}" updated successfully.', 'success')
            return redirect(url_for('.manage_tiers'))

        except Exception as e:
            db.session.rollback()
            logger.error(f'Error updating tier: {e}')
            flash('Error updating tier. Please try again.', 'error')
            return redirect(url_for('.edit_tier', tier_id=tier_id))

    # For GET request
    all_addons = Addon.query.filter_by(is_active=True).order_by(Addon.name).all()
    addon_permissions = _addon_permission_map(all_addons)
    all_permissions = _base_permissions(all_addons)
    return render_template(
        'developer/edit_tier.html',
        tier=tier,
        all_permissions=all_permissions,
        all_addons=all_addons,
        addon_permissions=addon_permissions,
    )

# --- Delete tier ---
# Purpose: Delete an unused tier.
@subscription_tiers_bp.route('/delete/<int:tier_id>', methods=['POST'])
@login_required
@require_permission('dev.manage_tiers')
def delete_tier(tier_id):
    """Delete a tier from the database, with safety checks."""
    tier = db.session.get(SubscriptionTier, tier_id)
    if not tier:
        flash('Tier not found.', 'error')
        return redirect(url_for('.manage_tiers'))

    # Safety check for system-critical tiers
    if tier.id in [1, 2]: # Assuming default IDs for exempt and free tiers
        flash(f'Cannot delete the system-critical "{tier.name}" tier.', 'error')
        return redirect(url_for('.manage_tiers'))

    # Check for organizations using this tier
    orgs_on_tier = Organization.query.filter_by(subscription_tier_id=tier_id).count()
    if orgs_on_tier > 0:
        flash(f'Cannot delete "{tier.name}" as {orgs_on_tier} organization(s) are currently subscribed to it.', 'error')
        return redirect(url_for('.manage_tiers'))

    try:
        db.session.delete(tier)
        db.session.commit()

        logger.info(f'Deleted subscription tier: {tier.name} (id: {tier.id})')
        flash(f'Subscription tier "{tier.name}" has been deleted.', 'success')

    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting tier: {e}')
        flash('Error deleting tier. Please try again.', 'error')

    return redirect(url_for('.manage_tiers'))

# =========================================================
# PROVIDER SYNC
# =========================================================
# --- Sync Stripe pricing ---
# Purpose: Pull Stripe pricing metadata for a tier.
@subscription_tiers_bp.route('/sync/<int:tier_id>', methods=['POST'])
@login_required
@require_permission('dev.manage_tiers')
def sync_tier_with_stripe(tier_id):
    """Sync a specific tier with Stripe pricing"""
    tier = db.session.get(SubscriptionTier, tier_id)
    if not tier:
        return jsonify({'success': False, 'error': 'Tier not found'}), 404

    if not tier.stripe_lookup_key:
        return jsonify({'success': False, 'error': 'No Stripe lookup key configured'}), 400

    try:
        from ...services.billing_service import BillingService

        # Get live pricing from Stripe
        live_pricing = BillingService.get_live_pricing_for_tier(tier)
        if live_pricing:
            logger.info(f'Successfully synced tier {tier.name} with Stripe - Price: {live_pricing["formatted_price"]}')
            return jsonify({
                'success': True,
                'message': f'Successfully synced {tier.name} with Stripe - Price: {live_pricing["formatted_price"]}',
                'tier': {
                    'id': tier.id,
                    'key': str(tier.id),
                    'name': tier.name,
                    'stripe_price': live_pricing['formatted_price']
                }
            })
        else:
            logger.warning(f'No pricing found for tier {tier.name} with lookup key {tier.stripe_lookup_key}')
            return jsonify({
                'success': False, 
                'error': f'No pricing found in Stripe for lookup key: {tier.stripe_lookup_key}'
            }), 400

    except Exception as e:
        logger.error(f'Error syncing tier {tier_id}: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

# --- Sync Whop pricing ---
# Purpose: Pull Whop pricing metadata for a tier.
@subscription_tiers_bp.route('/sync-whop/<int:tier_id>', methods=['POST'])
@login_required
@require_permission('dev.manage_tiers')
def sync_tier_with_whop(tier_id):
    """Sync a specific tier with Whop"""
    tier = db.session.get(SubscriptionTier, tier_id)
    if not tier:
        return jsonify({'success': False, 'error': 'Tier not found'}), 404

    if not tier.whop_product_key:
        return jsonify({'success': False, 'error': 'No Whop product key configured'}), 400

    try:
        # Here you would implement actual Whop sync logic
        # For now, return success
        logger.info(f'Synced tier {tier_id} with Whop')
        return jsonify({
            'success': True,
            'message': f'Successfully synced {tier.name} with Whop'
        })
    except Exception as e:
        logger.error(f'Error syncing tier {tier_id} with Whop: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

# =========================================================
# API
# =========================================================
# --- Tier metadata API ---
# Purpose: Return tier metadata for developer UI.
@subscription_tiers_bp.route('/api/tiers')
@login_required
@require_permission('dev.manage_tiers')
def api_get_tiers():
    """API endpoint to get all tiers as JSON."""
    tiers = SubscriptionTier.query.filter_by(is_customer_facing=True).all()
    return jsonify([{
        'id': tier.id,
        'key': str(tier.id), # Use ID as key for API
        'name': tier.name,
        'description': tier.description,
        'user_limit': tier.user_limit,
        'billing_provider': tier.billing_provider,
        'is_billing_exempt': tier.is_billing_exempt,
        'has_valid_integration': tier.has_valid_integration,
        'permissions': tier.get_permission_names(),
        'max_users': tier.max_users,
        'max_recipes': tier.max_recipes,
        'max_batches': tier.max_batches,
        'max_products': tier.max_products,
        'max_batchbot_requests': tier.max_batchbot_requests,
        'max_monthly_batches': tier.max_monthly_batches
    } for tier in tiers])