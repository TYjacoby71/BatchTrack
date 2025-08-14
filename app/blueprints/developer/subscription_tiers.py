from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, Permission, SubscriptionTier
from app.extensions import db
from app.utils.timezone_utils import TimezoneUtils
import json
import os
import logging

logger = logging.getLogger(__name__)

subscription_tiers_bp = Blueprint('subscription_tiers', __name__, url_prefix='/subscription-tiers')

# Load/save tier configuration
TIERS_CONFIG_FILE = 'subscription_tiers.json'

def load_tiers_config():
    """Load subscription tiers from JSON file - this is the single source of truth"""
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

def save_tiers_config(tiers):
    """Save subscription tiers to JSON file"""
    with open(TIERS_CONFIG_FILE, 'w') as f:
        json.dump(tiers, f, indent=2)

def sync_tier_to_database(tier_key, tier_config):
    """Sync a tier configuration to the database"""
    # Skip exempt tier - it's handled by seeder
    if tier_key == 'exempt':
        return

    # Find or create tier record
    tier_record = SubscriptionTier.query.filter_by(key=tier_key).first()
    if not tier_record:
        tier_record = SubscriptionTier(key=tier_key)
        db.session.add(tier_record)

    # Update tier fields
    tier_record.name = tier_config.get('name', tier_key.title())
    tier_record.description = tier_config.get('description', '')
    tier_record.user_limit = tier_config.get('user_limit', 1)
    tier_record.is_customer_facing = tier_config.get('is_customer_facing', True)
    
    # New billing configuration
    tier_record.billing_provider = tier_config.get('billing_provider', 'exempt')
    tier_record.is_billing_exempt = tier_config.get('is_billing_exempt', False)

    # Integration keys for linking to external products
    stripe_lookup_key = tier_config.get('stripe_lookup_key')
    if stripe_lookup_key is not None:
        tier_record.stripe_lookup_key = stripe_lookup_key

    whop_product_key = tier_config.get('whop_product_key')
    if whop_product_key is not None:
        tier_record.whop_product_key = whop_product_key

    tier_record.fallback_price = tier_config.get('fallback_price', '$0')

    # Handle permissions
    permission_names = tier_config.get('permissions', [])
    permissions = Permission.query.filter(Permission.name.in_(permission_names)).all()
    tier_record.permissions = permissions

    db.session.commit()

    return tier_record

@subscription_tiers_bp.route('/')
@login_required
def manage_tiers():
    """Main subscription tiers management page"""
    tiers = load_tiers_config()
    all_permissions = Permission.query.filter_by(is_active=True).all()

    # Ensure each tier has proper pricing display data
    for tier_key, tier_data in tiers.items():
        # Ensure fallback price is displayed if no Stripe price
        if not tier_data.get('stripe_price') and not tier_data.get('fallback_price'):
            tier_data['fallback_price'] = '$0'

    return render_template('developer/subscription_tiers.html',
                         tiers=tiers,
                         all_permissions=all_permissions)

def create_stripe_secrets(tier_key, monthly_price_id, yearly_price_id):
    """Create environment secrets for Stripe price IDs"""
    import os

    # Create secret names following the convention
    monthly_secret_name = f'STRIPE_{tier_key.upper()}_MONTHLY_PRICE_ID'
    yearly_secret_name = f'STRIPE_{tier_key.upper()}_YEARLY_PRICE_ID'

    # In Replit, we can set environment variables dynamically (they become secrets)
    if monthly_price_id:
        os.environ[monthly_secret_name] = monthly_price_id
        logger.info(f"Created secret: {monthly_secret_name}")

    if yearly_price_id:
        os.environ[yearly_secret_name] = yearly_price_id
        logger.info(f"Created secret: {yearly_secret_name}")

    return monthly_secret_name, yearly_secret_name

@subscription_tiers_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_tier():
    """Create a new subscription tier with dynamic secret management"""
    if request.method == 'POST':
        tier_key = request.form.get('tier_key')
        tier_name = request.form.get('tier_name')

        if not tier_key or not tier_name:
            flash('Tier key and name are required', 'error')
            return redirect(url_for('developer.subscription_tiers.manage_tiers'))

        tiers = load_tiers_config()

        if tier_key in tiers:
            flash('Tier key already exists', 'error')
            return redirect(url_for('developer.subscription_tiers.manage_tiers'))

        # Get Stripe price IDs and create secrets
        monthly_price_id = request.form.get('stripe_monthly_price_id', '').strip()
        yearly_price_id = request.form.get('stripe_yearly_price_id', '').strip()

        # Create secrets for the price IDs if provided
        if monthly_price_id or yearly_price_id:
            try:
                monthly_secret, yearly_secret = create_stripe_secrets(tier_key, monthly_price_id, yearly_price_id)
                flash(f'Stripe secrets created: {monthly_secret}, {yearly_secret}', 'info')
            except Exception as e:
                flash(f'Warning: Could not create Stripe secrets: {str(e)}', 'warning')

        # Get billing configuration
        billing_provider = request.form.get('billing_provider', 'exempt')
        is_billing_exempt = request.form.get('is_billing_exempt') == 'on'
        
        # Validate integration requirements
        if not is_billing_exempt and billing_provider != 'exempt':
            if billing_provider == 'stripe' and not request.form.get('stripe_lookup_key', '').strip():
                flash('Stripe lookup key is required for Stripe billing', 'error')
                return redirect(url_for('developer.subscription_tiers.create_tier'))
            elif billing_provider == 'whop' and not request.form.get('whop_product_key', '').strip():
                flash('Whop product key is required for Whop billing', 'error')
                return redirect(url_for('developer.subscription_tiers.create_tier'))

        # Get form data
        fallback_features = [f.strip() for f in request.form.get('fallback_features', '').split('\n') if f.strip()]
        user_limit = int(request.form.get('user_limit', 1))

        new_tier = {
            'name': tier_name,
            'permissions': [],  # Will be configured on edit page - system access control
            'stripe_lookup_key': request.form.get('stripe_lookup_key', '') if billing_provider == 'stripe' else '',
            'whop_product_key': request.form.get('whop_product_key', '') if billing_provider == 'whop' else '',
            'user_limit': user_limit,
            'is_customer_facing': request.form.get('is_customer_facing') == 'on',
            'billing_provider': billing_provider,
            'is_billing_exempt': is_billing_exempt,
            'fallback_features': fallback_features,  # Customer-facing features for display
            'fallback_price': request.form.get('fallback_price', '$0'),
            'stripe_features': [],  # Features from Stripe product data
            'stripe_price': None,
            'last_synced': None,
            # Store secret references, not the actual IDs
            'stripe_monthly_secret': f'STRIPE_{tier_key.upper()}_MONTHLY_PRICE_ID' if monthly_price_id else None,
            'stripe_yearly_secret': f'STRIPE_{tier_key.upper()}_YEARLY_PRICE_ID' if yearly_price_id else None
        }

        tiers[tier_key] = new_tier
        save_tiers_config(tiers)

        # Also create/update database record
        sync_tier_to_database(tier_key, new_tier)

        flash(f'Subscription tier "{tier_name}" created successfully with Stripe integration', 'success')
        return redirect(url_for('developer.subscription_tiers.manage_tiers'))

    return render_template('developer/create_tier.html')

@subscription_tiers_bp.route('/edit/<tier_key>', methods=['GET', 'POST'])
@login_required
def edit_tier(tier_key):
    """Edit an existing subscription tier"""
    tiers = load_tiers_config()

    if tier_key not in tiers:
        flash('Tier not found', 'error')
        return redirect(url_for('developer.subscription_tiers.manage_tiers'))

    if request.method == 'POST':
        tier = tiers[tier_key]

        # Get billing configuration
        billing_provider = request.form.get('billing_provider', 'exempt')
        is_billing_exempt = request.form.get('is_billing_exempt') == 'on'
        
        # Validate integration requirements
        if not is_billing_exempt and billing_provider != 'exempt':
            if billing_provider == 'stripe' and not request.form.get('stripe_lookup_key', '').strip():
                flash('Stripe lookup key is required for Stripe billing', 'error')
                return redirect(url_for('developer.subscription_tiers.edit_tier', tier_key=tier_key))
            elif billing_provider == 'whop' and not request.form.get('whop_product_key', '').strip():
                flash('Whop product key is required for Whop billing', 'error')
                return redirect(url_for('developer.subscription_tiers.edit_tier', tier_key=tier_key))

        # Update tier data from form
        tier['name'] = request.form.get('tier_name', tier['name'])
        tier['user_limit'] = int(request.form.get('user_limit', tier.get('user_limit', 1)))
        tier['is_customer_facing'] = 'is_customer_facing' in request.form
        tier['billing_provider'] = billing_provider
        tier['is_billing_exempt'] = is_billing_exempt

        tier['permissions'] = request.form.getlist('permissions')
        tier['stripe_lookup_key'] = request.form.get('stripe_lookup_key', '') if billing_provider == 'stripe' else ''
        tier['whop_product_key'] = request.form.get('whop_product_key', '') if billing_provider == 'whop' else ''

        tier['fallback_features'] = [f.strip() for f in request.form.get('fallback_features', '').split('\n') if f.strip()]
        tier['fallback_price'] = request.form.get('fallback_price', '$0')

        save_tiers_config(tiers)

        # Also update database record
        sync_tier_to_database(tier_key, tier)

        flash(f'Subscription tier "{tier["name"]}" updated successfully', 'success')
        return redirect(url_for('developer.subscription_tiers.manage_tiers'))

    tier = tiers[tier_key]
    all_permissions = Permission.query.filter_by(is_active=True).all()

    return render_template('developer/edit_tier.html',
                         tier_key=tier_key,
                         tier=tier,
                         permissions=all_permissions)

@subscription_tiers_bp.route('/delete/<tier_key>', methods=['POST'])
@login_required
def delete_tier(tier_key):
    """Delete a subscription tier"""
    if not current_user.is_developer:
        flash('Developer access required', 'error')
        return redirect(url_for('app_routes.dashboard'))

    tiers = load_tiers_config()

    if tier_key not in tiers:
        flash('Tier not found', 'error')
        return redirect(url_for('developer.subscription_tiers.manage_tiers'))

    # Only prevent deletion of exempt tier (system dependency)
    if tier_key == 'exempt':
        flash(f'Cannot delete {tier_key} tier - it is required for system operation', 'error')
        return redirect(url_for('developer.subscription_tiers.manage_tiers'))

    # Check if any organizations are currently using this tier
    from app.models import Organization
    organizations_using_tier = Organization.query.filter_by(subscription_tier=tier_key).all()

    if organizations_using_tier:
        org_names = [org.name for org in organizations_using_tier[:5]]  # Show first 5
        if len(organizations_using_tier) > 5:
            org_list = ', '.join(org_names) + f' and {len(organizations_using_tier) - 5} others'
        else:
            org_list = ', '.join(org_names)

        flash(f'Cannot delete "{tiers[tier_key]["name"]}" tier - it is currently being used by {len(organizations_using_tier)} organization(s): {org_list}. Please migrate these organizations to different tiers first.', 'error')
        return redirect(url_for('developer.subscription_tiers.manage_tiers'))

    tier_name = tiers[tier_key]['name']
    del tiers[tier_key]
    save_tiers_config(tiers)

    # Also remove from database
    tier_record = SubscriptionTier.query.filter_by(key=tier_key).first()
    if tier_record:
        db.session.delete(tier_record)
        db.session.commit()

    flash(f'Subscription tier "{tier_name}" deleted successfully', 'success')
    return redirect(url_for('developer.subscription_tiers.manage_tiers'))

@subscription_tiers_bp.route('/sync/<tier_key>', methods=['POST'])
@login_required
def sync_tier(tier_key):
    """Validate tier configuration and sync to database, fetch pricing from Stripe"""
    tiers = load_tiers_config()

    if tier_key not in tiers:
        return jsonify({'error': 'Tier not found'}), 404

    tier_config = tiers[tier_key] # Renamed from 'tier' to 'tier_config' for clarity
    stripe_lookup_key = tier_config.get('stripe_lookup_key')

    try:
        # Sync the tier configuration to database
        sync_tier_to_database(tier_key, tier_config)

        # If tier has Stripe lookup key, fetch pricing from Stripe
        if stripe_lookup_key:
            try:
                from app.services.stripe_service import StripeService
                # Get the tier object and fetch live pricing
                tier_obj = SubscriptionTier.query.filter_by(key=tier_key).first()
                if tier_obj:
                    pricing_data = StripeService.get_live_pricing_for_tier(tier_obj)

                if pricing_data:
                        # Update the tier config with fresh pricing data
                        tier_config['stripe_price'] = pricing_data.get('formatted_price', '')
                        tier_config['stripe_price_id'] = pricing_data.get('price_id', '')
                        tier_config['last_synced'] = TimezoneUtils.utc_now().isoformat()

                        # Update fallback price from Stripe pricing
                        tier_config['fallback_price'] = pricing_data.get('formatted_price', tier_config.get('fallback_price', '$0'))

                        logger.info(f"Updated pricing for tier {tier_key}: {pricing_data.get('formatted_price', 'N/A')}")
                else:
                    logger.warning(f"No Stripe pricing found for lookup key: {stripe_lookup_key}")
            except Exception as e:
                logger.error(f"Error fetching Stripe pricing for {tier_key}: {e}")

        # Sync tier to database using only the fields that exist in the model
        try:
            tier_obj = SubscriptionTier.query.filter_by(key=tier_key).first()
            if not tier_obj:
                tier_obj = SubscriptionTier(key=tier_key)
                db.session.add(tier_obj)

            # Update only the fields that actually exist in the SubscriptionTier model
            tier_obj.name = tier_config.get('name', tier_key.title())
            tier_obj.description = tier_config.get('description', '')
            tier_obj.user_limit = tier_config.get('user_limit', 1)
            tier_obj.is_customer_facing = tier_config.get('is_customer_facing', True)
            tier_obj.is_available = tier_config.get('is_available', True)
            tier_obj.tier_type = tier_config.get('tier_type', 'paid')
            tier_obj.billing_provider = tier_config.get('billing_provider')

            # Handle nullable fields safely
            stripe_lookup_key = tier_config.get('stripe_lookup_key')
            if stripe_lookup_key:
                tier_obj.stripe_lookup_key = stripe_lookup_key

            whop_product_key = tier_config.get('whop_product_key')
            if whop_product_key:
                tier_obj.whop_product_key = whop_product_key

            tier_obj.fallback_price = tier_config.get('fallback_price', '$0')

            # Handle permissions relationship
            permission_names = tier_config.get('permissions', [])
            if permission_names:
                from app.models import Permission
                permissions = Permission.query.filter(Permission.name.in_(permission_names)).all()
                tier_obj.permissions = permissions

            db.session.commit()
            logger.info(f"Synced tier to database: {tier_key}")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error syncing tier {tier_key} to database: {e}")
            return jsonify({'success': False, 'error': f'Database sync failed: {str(e)}'}), 500

        # Save updated pricing and other config changes back to JSON if they occurred
        save_tiers_config(tiers)

        return jsonify({
            'success': True,
            'tier': tier_config,
            'message': f'Successfully synced {tier_config["name"]} configuration' +
                       (f' with Stripe pricing' if stripe_lookup_key else '')
        })

    except Exception as e:
        logger.error(f"Unexpected error during sync of tier {tier_key}: {str(e)}")
        return jsonify({'success': False, 'error': f'Sync failed: {str(e)}'}), 500


@subscription_tiers_bp.route('/api/tiers')
@login_required
def api_get_tiers():
    """API endpoint to get current tiers configuration"""
    return jsonify(load_tiers_config())

@subscription_tiers_bp.route('/sync-whop/<tier_key>', methods=['POST'])
@login_required
def sync_whop_tier(tier_key):
    """Validate Whop product configuration"""
    tiers = load_tiers_config()

    if tier_key not in tiers:
        return jsonify({'error': 'Tier not found'}), 404

    tier = tiers[tier_key]
    whop_product_key = tier.get('whop_product_key')

    if not whop_product_key:
        return jsonify({'error': 'No Whop product key configured'}), 400

    try:
        # Just validate the configuration and sync to database
        sync_tier_to_database(tier_key, tier)

        return jsonify({
            'success': True,
            'tier': tier,
            'message': f'Successfully validated Whop configuration for {tier["name"]}'
        })

    except Exception as e:
        return jsonify({'error': f'Whop validation failed: {str(e)}'}), 500

@subscription_tiers_bp.route('/api/customer-tiers')
def api_get_customer_tiers():
    """API endpoint to get customer-facing tiers only"""
    all_tiers = load_tiers_config()
    customer_tiers = {
        key: tier for key, tier in all_tiers.items()
        if tier.get('is_customer_facing', True) and tier.get('is_available', True)
    }
    return jsonify(customer_tiers)

@subscription_tiers_bp.route('/api/tiers/by-category/<category>')
def api_get_tiers_by_category(category):
    """API endpoint to get tiers by pricing category"""
    all_tiers = load_tiers_config()
    filtered_tiers = {
        key: tier for key, tier in all_tiers.items()
        if (tier.get('pricing_category', 'standard') == category and
            tier.get('is_customer_facing', True) and
            tier.get('is_available', True))
    }
    return jsonify(filtered_tiers)