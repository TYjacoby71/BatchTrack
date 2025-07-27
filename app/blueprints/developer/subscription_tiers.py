from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, Permission, SubscriptionTier
from app.extensions import db
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
    tier_record.name = tier_config.get('name', tier_key)
    tier_record.description = tier_config.get('description', '')
    tier_record.user_limit = tier_config.get('user_limit', 1)
    tier_record.is_customer_facing = tier_config.get('is_customer_facing', True)
    tier_record.is_available = tier_config.get('is_available', True)

    # Only update stripe_lookup_key if it's actually provided in config
    # This preserves manually set lookup keys from being overwritten
    lookup_key_from_config = tier_config.get('stripe_lookup_key')
    if lookup_key_from_config is not None:
        tier_record.stripe_lookup_key = lookup_key_from_config

    tier_record.fallback_price_monthly = tier_config.get('fallback_price_monthly', '$0')
    tier_record.fallback_price_yearly = tier_config.get('fallback_price_yearly', '$0')

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

    return render_template('developer/subscription_tiers.html', 
                         tiers=tiers,
                         all_permissions=all_permissions)

@subscription_tiers_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_tier():
    """Create a new subscription tier"""
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

        # Get form data
        permissions = request.form.getlist('permissions')
        fallback_features = [f.strip() for f in request.form.get('fallback_features', '').split('\n') if f.strip()]

        user_limit = int(request.form.get('user_limit', 1))
        # Only exempt tier can have unlimited users (-1)

        new_tier = {
            'name': tier_name,
            'permissions': permissions,
            'feature_groups': request.form.getlist('feature_groups'),
            'stripe_lookup_key': request.form.get('stripe_lookup_key', ''),
            'user_limit': user_limit,
            'is_customer_facing': request.form.get('is_customer_facing') == 'on',
            'is_available': request.form.get('is_available') == 'on',
            'fallback_features': fallback_features,
            'fallback_price_monthly': request.form.get('fallback_price_monthly', '$0'),
            'fallback_price_yearly': request.form.get('fallback_price_yearly', '$0'),
            'stripe_features': [],
            'stripe_price_monthly': None,
            'stripe_price_yearly': None,
            'last_synced': None
        }

        tiers[tier_key] = new_tier
        save_tiers_config(tiers)

        # Also create/update database record
        sync_tier_to_database(tier_key, new_tier)

        flash(f'Subscription tier "{tier_name}" created successfully', 'success')
        return redirect(url_for('developer.subscription_tiers.manage_tiers'))

    all_permissions = Permission.query.filter_by(is_active=True).all()
    return render_template('developer/create_tier.html', permissions=all_permissions)

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

        # Update tier data from form
        tier['name'] = request.form.get('tier_name', tier['name'])
        tier['user_limit'] = int(request.form.get('user_limit', tier.get('user_limit', 1)))
        tier['is_customer_facing'] = 'is_customer_facing' in request.form
        tier['is_available'] = 'is_available' in request.form


        tier['permissions'] = request.form.getlist('permissions')
        tier['feature_groups'] = request.form.getlist('feature_groups')
        tier['stripe_lookup_key'] = request.form.get('stripe_lookup_key', '')

        user_limit_str = request.form.get('user_limit', '1')
        try:
            user_limit = int(user_limit_str)
        except (ValueError, TypeError):
            user_limit = 1  # Default fallback

        tier['user_limit'] = user_limit

        # Update visibility controls
        tier['is_customer_facing'] = request.form.get('is_customer_facing') == 'on'
        tier['is_available'] = request.form.get('is_available') == 'on'

        tier['fallback_features'] = [f.strip() for f in request.form.get('fallback_features', '').split('\n') if f.strip()]
        tier['fallback_price_monthly'] = request.form.get('fallback_price_monthly', '$0')
        tier['fallback_price_yearly'] = request.form.get('fallback_price_yearly', '$0')

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
    # Prevent deletion of system tiers
    if tier_key in ['free', 'exempt']:
        flash(f'Cannot delete system tier: {tier_key}', 'error')
        return redirect(url_for('developer.subscription_tiers.manage_tiers'))

    tiers = load_tiers_config()

    if tier_key not in tiers:
        flash('Tier not found', 'error')
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
    """Sync a tier with Stripe pricing and features - resilient to failures"""
    import stripe
    from datetime import datetime

    tiers = load_tiers_config()

    if tier_key not in tiers:
        return jsonify({'error': 'Tier not found'}), 404

    tier = tiers[tier_key]
    lookup_key = tier.get('stripe_lookup_key')

    if not lookup_key:
        return jsonify({'error': 'No Stripe lookup key configured'}), 400

    try:
        # Initialize Stripe
        stripe_key = os.environ.get('STRIPE_SECRET_KEY')
        if not stripe_key:
            return jsonify({'error': 'Stripe secret key not configured in secrets'}), 400

        stripe.api_key = stripe_key
        logger.info(f"Stripe initialized for sync of tier {tier_key} with lookup key: {lookup_key}")

        # Wrap the entire sync operation in try-catch to ensure failures are contained
        try:
            product = None
            
            # Method 1: Find by lookup key in prices (most reliable)
            try:
                prices = stripe.Price.list(lookup_keys=[lookup_key], limit=1, active=True)
                if prices.data:
                    price = prices.data[0]
                    product = stripe.Product.retrieve(price.product)
                    logger.info(f"Found product via lookup key '{lookup_key}': {product.name} (ID: {product.id})")
            except stripe.error.StripeError as lookup_error:
                logger.warning(f"Lookup key search failed for '{lookup_key}': {str(lookup_error)}")
            
            # Method 2: If lookup key failed, fall back to name matching
            if not product:
                logger.info(f"Lookup key '{lookup_key}' not found, falling back to name matching")
                try:
                    all_products = stripe.Product.list(limit=100, active=True)
                    
                    # Try to match by product name containing tier key
                    tier_name_variations = [
                        f"BatchTrack {tier_key.title()}",  # "BatchTrack Solo"
                        f"BatchTrack {tier['name']}",      # "BatchTrack Solo Plan"
                        tier_key.title(),                  # "Solo"
                        tier['name']                       # "Solo Plan"
                    ]

                    logger.info(f"Searching for product matching tier '{tier_key}' in {len(all_products.data)} products")

                    for p in all_products.data:
                        logger.info(f"Checking product: {p.name} (ID: {p.id})")
                        # Try name matching
                        for name_variation in tier_name_variations:
                            if name_variation.lower() in p.name.lower():
                                product = p
                                logger.info(f"Found matching product: {p.name} for variation: {name_variation}")
                                break
                        if product:
                            break
                except stripe.error.StripeError as product_list_error:
                    logger.error(f"Failed to list products for name matching: {str(product_list_error)}")

            if not product:
                # Don't fail the entire operation - just return a warning
                logger.warning(f"No Stripe product found for tier: {tier_key} (lookup key: {lookup_key})")
                return jsonify({
                    'success': False,
                    'error': f'No Stripe product found for tier: {tier_key} (lookup key: {lookup_key}). Check your Stripe dashboard.',
                    'tier': tier,
                    'fallback_used': True
                }), 404

            logger.info(f"Found Stripe product: {product.id} ({product.name})")

        except stripe.error.StripeError as search_error:
            logger.error(f"Stripe API failed for lookup key {lookup_key}: {str(search_error)}")
            return jsonify({
                'success': False,
                'error': f'Stripe API error: {str(search_error)}',
                'tier': tier,
                'fallback_used': True
            }), 400

        # Get prices for this product
        try:
            # First check if product has a default price
            monthly_price = None
            yearly_price = None
            monthly_price_id = None
            yearly_price_id = None

            if product.default_price:
                # Expand the default price to get full details
                default_price = stripe.Price.retrieve(product.default_price)
                if default_price.recurring:
                    if default_price.recurring.interval == 'month':
                        monthly_price = f"${default_price.unit_amount / 100:.0f}"
                        monthly_price_id = default_price.id
                    elif default_price.recurring.interval == 'year':
                        yearly_price = f"${default_price.unit_amount / 100:.0f}"
                        yearly_price_id = default_price.id

            # Also check for additional prices
            prices = stripe.Price.list(product=product.id, active=True)
            for price in prices.data:
                if price.recurring:
                    # Monthly price (interval = month, interval_count = 1)
                    if (price.recurring.interval == 'month' and 
                        price.recurring.interval_count == 1 and 
                        not monthly_price_id):
                        monthly_price = f"${price.unit_amount / 100:.0f}"
                        monthly_price_id = price.id
                    # Yearly price (interval = month, interval_count = 12 OR interval = year)
                    elif ((price.recurring.interval == 'month' and price.recurring.interval_count == 12) or
                          (price.recurring.interval == 'year')) and not yearly_price_id:
                        yearly_price = f"${price.unit_amount / 100:.0f}"
                        yearly_price_id = price.id

            logger.info(f"Found prices - Monthly: {monthly_price} ({monthly_price_id}), Yearly: {yearly_price} ({yearly_price_id})")

        except stripe.error.StripeError as price_error:
            logger.error(f"Failed to fetch prices for product {product.id}: {str(price_error)}")
            return jsonify({'error': f'Failed to fetch prices: {str(price_error)}'}), 400

        # Extract features from product metadata or description
        features = []
        if product.metadata.get('features'):
            features = product.metadata['features'].split(',')
        elif product.description:
            # Try to extract features from description
            features = [f.strip() for f in product.description.split(',') if f.strip()]

        # Update tier with Stripe data - NEVER overwrite manually set lookup key
        tier['stripe_features'] = features
        tier['stripe_price_monthly'] = monthly_price or tier.get('fallback_price_monthly', '$0')
        tier['stripe_price_yearly'] = yearly_price or tier.get('fallback_price_yearly', '$0')
        tier['stripe_price_id_monthly'] = monthly_price_id
        tier['stripe_price_id_yearly'] = yearly_price_id
        tier['last_synced'] = datetime.now().isoformat()

        # Preserve existing stripe_lookup_key - this is the user's manual configuration
        # and should NEVER be overwritten by sync operations
        
        # Ensure the lookup key is preserved in the tier data
        if not tier.get('stripe_lookup_key'):
            logger.warning(f"No stripe_lookup_key found for tier {tier_key} - this should be set manually")

        # Update pricing snapshots for resilience
        try:
            from ...models.pricing_snapshot import PricingSnapshot
            
            # Create/update snapshots for both monthly and yearly prices
            if monthly_price_id:
                monthly_price_data = stripe.Price.retrieve(monthly_price_id)
                PricingSnapshot.update_from_stripe_data(monthly_price_data, product)
                logger.info(f"Updated pricing snapshot for monthly price: {monthly_price_id}")
            
            if yearly_price_id:
                yearly_price_data = stripe.Price.retrieve(yearly_price_id)
                PricingSnapshot.update_from_stripe_data(yearly_price_data, product)
                logger.info(f"Updated pricing snapshot for yearly price: {yearly_price_id}")
                
            db.session.commit()
            logger.info(f"Pricing snapshots updated for tier {tier_key}")
            
        except Exception as snapshot_error:
            logger.warning(f"Failed to update pricing snapshots for tier {tier_key}: {str(snapshot_error)}")
            # Don't fail the sync if snapshots fail

        save_tiers_config(tiers)

        # Also update database record with the current lookup key
        sync_tier_to_database(tier_key, tier)

        logger.info(f"Synced tier {tier_key} with Stripe - preserved lookup key: {lookup_key}")

        return jsonify({
            'success': True,
            'tier': tier,
            'message': f'Successfully synced {tier["name"]} with Stripe (lookup key preserved)'
        })

    except stripe.error.StripeError as e:
        return jsonify({'error': f'Stripe error: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Sync failed: {str(e)}'}), 500

@subscription_tiers_bp.route('/api/tiers')
@login_required 
def api_get_tiers():
    """API endpoint to get current tiers configuration"""
    return jsonify(load_tiers_config())

@subscription_tiers_bp.route('/api/customer-tiers')
def api_get_customer_tiers():
    """API endpoint to get customer-facing tiers only"""
    all_tiers = load_tiers_config()
    customer_tiers = {
        key: tier for key, tier in all_tiers.items() 
        if tier.get('is_customer_facing', True) and tier.get('is_available', True)
    }
    return jsonify(customer_tiers)