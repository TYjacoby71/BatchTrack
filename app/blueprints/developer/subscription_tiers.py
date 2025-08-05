from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app.models import db, Permission, SubscriptionTier
# from app.extensions import db # Removed duplicate import
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
    logger.warning("No subscription_tiers.json found - tiers must be configured in JSON file")
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
    tier_record.is_available = tier_config.get('is_available', True)
    tier_record.requires_stripe_billing = tier_config.get('requires_stripe_billing', False) # Default to False if not specified
    tier_record.requires_whop_billing = tier_config.get('requires_whop_billing', False) # Default to False if not specified


    # Only update stripe_lookup_key if it's actually provided in config
    # This preserves manually set lookup keys from being overwritten
    lookup_key_from_config = tier_config.get('stripe_lookup_key')
    if lookup_key_from_config is not None:
        tier_record.stripe_lookup_key = lookup_key_from_config
    
    # Update Whop keys if provided
    whop_product_key_from_config = tier_config.get('whop_product_key')
    if whop_product_key_from_config is not None:
        tier_record.whop_product_key = whop_product_key_from_config
    
    whop_product_name_from_config = tier_config.get('whop_product_name')
    if whop_product_name_from_config is not None:
        tier_record.whop_product_name = whop_product_name_from_config

    # Tier fallback prices
    tier_record.fallback_price_monthly = tier_config.get('fallback_price_monthly', '$0')
    tier_record.fallback_price_yearly = tier_config.get('fallback_price_yearly', '$0')

    # Handle permissions
    permission_names = tier_config.get('permissions', [])
    # Ensure we only add valid permissions that exist in the Permission table
    existing_permissions = Permission.query.filter(Permission.name.in_(permission_names), Permission.is_active == True).all()
    tier_record.permissions = existing_permissions

    db.session.commit()

    return tier_record

@subscription_tiers_bp.route('/')
@login_required
def manage_tiers():
    """Main subscription tiers management page"""
    tiers = load_tiers_config()
    all_permissions = Permission.query.filter_by(is_active=True).all()

    # Group permissions by category for better display
    permissions_by_category = {}
    for perm in all_permissions:
        category = perm.category if perm.category else 'Uncategorized'
        if category not in permissions_by_category:
            permissions_by_category[category] = []
        permissions_by_category[category].append(perm)
    
    # Sort categories and permissions within categories
    sorted_categories = sorted(permissions_by_category.keys())
    for category in sorted_categories:
        permissions_by_category[category].sort(key=lambda p: p.name)

    return render_template('developer/subscription_tiers.html', 
                         tiers=tiers,
                         all_permissions=all_permissions, # Keep this for potential direct use in template
                         permissions_by_category=permissions_by_category,
                         sorted_categories=sorted_categories)

@subscription_tiers_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_tier():
    """Create a new subscription tier"""
    if request.method == 'POST':
        try:
            # Get form data
            tier_key = request.form.get('tier_key', '').strip().lower()
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            user_limit_str = request.form.get('user_limit', '1').strip()

            # Basic validation
            if not tier_key or not name:
                flash('Tier key and name are required.', 'error')
                return redirect(url_for('subscription_tiers.create_tier'))

            # Validate user_limit
            try:
                user_limit = int(user_limit_str)
                if user_limit <= 0:
                    raise ValueError("User limit must be a positive integer.")
            except (ValueError, TypeError) as e:
                flash(f'Invalid user limit: {str(e)}', 'error')
                return redirect(url_for('subscription_tiers.create_tier'))

            # Load existing tiers to check for duplicates
            tiers = load_tiers_config()

            if tier_key in tiers:
                flash(f'Tier "{tier_key}" already exists!', 'error')
                return redirect(url_for('subscription_tiers.create_tier'))

            # Get selected permissions
            selected_permissions = request.form.getlist('permissions')

            # Get billing configuration
            requires_stripe_billing = request.form.get('requires_stripe_billing') == 'on'
            requires_whop_billing = request.form.get('requires_whop_billing') == 'on'

            # Create new tier configuration
            new_tier = {
                'name': name,
                'description': description,
                'user_limit': user_limit,
                'is_customer_facing': request.form.get('is_customer_facing') == 'on',
                'is_available': request.form.get('is_available') == 'on',
                'requires_stripe_billing': requires_stripe_billing,
                'requires_whop_billing': requires_whop_billing,
                'fallback_price_monthly': request.form.get('fallback_price_monthly', '$0').strip(),
                'fallback_price_yearly': request.form.get('fallback_price_yearly', '$0').strip(),
                'permissions': selected_permissions
            }

            # Add billing-specific fields if enabled
            if requires_stripe_billing:
                new_tier['stripe_lookup_key'] = request.form.get('stripe_lookup_key', '').strip()
                # Add other Stripe specific fields if needed like price, currency etc.
                new_tier['stripe_price_monthly'] = request.form.get('stripe_price_monthly', '') # Example for direct price input
                new_tier['stripe_price_yearly'] = request.form.get('stripe_price_yearly', '') # Example for direct price input
                new_tier['currency'] = request.form.get('currency', 'USD')


            if requires_whop_billing:
                new_tier['whop_product_key'] = request.form.get('whop_product_key', '').strip()
                new_tier['whop_product_name'] = request.form.get('whop_product_name', '').strip()

            # Add to tiers config
            tiers[tier_key] = new_tier
            save_tiers_config(tiers)

            # Sync to database
            sync_tier_to_database(tier_key, new_tier)

            flash(f'Subscription tier "{name}" created successfully with {len(selected_permissions)} permissions!', 'success')
            return redirect(url_for('subscription_tiers.manage_tiers'))

        except Exception as e:
            flash(f'Error creating tier: {str(e)}', 'error')
            logger.error(f"Error creating tier: {str(e)}")
            return redirect(url_for('subscription_tiers.create_tier'))

    # GET request - show form
    all_permissions = Permission.query.filter_by(is_active=True).all()
    # Group permissions by category for better display in the form
    permissions_by_category = {}
    for perm in all_permissions:
        category = perm.category if perm.category else 'Uncategorized'
        if category not in permissions_by_category:
            permissions_by_category[category] = []
        permissions_by_category[category].append(perm)
    
    # Sort categories and permissions within categories
    sorted_categories = sorted(permissions_by_category.keys())
    for category in sorted_categories:
        permissions_by_category[category].sort(key=lambda p: p.name)

    return render_template('developer/create_tier.html', 
                         all_permissions=all_permissions,
                         permissions_by_category=permissions_by_category,
                         sorted_categories=sorted_categories)

@subscription_tiers_bp.route('/edit/<tier_key>', methods=['GET', 'POST'])
@login_required
def edit_tier(tier_key):
    """Edit an existing subscription tier"""
    tiers = load_tiers_config()

    if tier_key not in tiers:
        flash('Tier not found', 'error')
        return redirect(url_for('subscription_tiers.manage_tiers'))

    if request.method == 'POST':
        tier = tiers[tier_key]

        try:
            # Update basic tier data
            tier['name'] = request.form.get('tier_name', tier.get('name', tier_key.title())).strip()
            tier['description'] = request.form.get('description', tier.get('description', '')).strip()
            user_limit_str = request.form.get('user_limit', str(tier.get('user_limit', 1))).strip()
            
            # Validate user_limit
            try:
                user_limit = int(user_limit_str)
                if user_limit <= 0:
                    raise ValueError("User limit must be a positive integer.")
                tier['user_limit'] = user_limit
            except (ValueError, TypeError) as e:
                flash(f'Invalid user limit: {str(e)}', 'error')
                return redirect(url_for('subscription_tiers.edit_tier', tier_key=tier_key))

            tier['is_customer_facing'] = request.form.get('is_customer_facing') == 'on'
            tier['is_available'] = request.form.get('is_available') == 'on'
            tier['requires_stripe_billing'] = request.form.get('requires_stripe_billing') == 'on'
            tier['requires_whop_billing'] = request.form.get('requires_whop_billing') == 'on'

            # Update permissions
            tier['permissions'] = request.form.getlist('permissions')

            # Update fallback pricing
            tier['fallback_price_monthly'] = request.form.get('fallback_price_monthly', tier.get('fallback_price_monthly', '$0')).strip()
            tier['fallback_price_yearly'] = request.form.get('fallback_price_yearly', tier.get('fallback_price_yearly', '$0')).strip()

            # Update billing-specific fields
            if tier['requires_stripe_billing']:
                tier['stripe_lookup_key'] = request.form.get('stripe_lookup_key', tier.get('stripe_lookup_key', '')).strip()
                tier['stripe_price_monthly'] = request.form.get('stripe_price_monthly', tier.get('stripe_price_monthly', ''))
                tier['stripe_price_yearly'] = request.form.get('stripe_price_yearly', tier.get('stripe_price_yearly', ''))
                tier['currency'] = request.form.get('currency', tier.get('currency', 'USD'))
            else:
                # Remove Stripe fields if billing is disabled
                tier.pop('stripe_lookup_key', None)
                tier.pop('stripe_price_monthly', None)
                tier.pop('stripe_price_yearly', None)
                tier.pop('currency', None)


            if tier['requires_whop_billing']:
                tier['whop_product_key'] = request.form.get('whop_product_key', tier.get('whop_product_key', '')).strip()
                tier['whop_product_name'] = request.form.get('whop_product_name', tier.get('whop_product_name', '')).strip()
            else:
                # Remove Whop fields if billing is disabled
                tier.pop('whop_product_key', None)
                tier.pop('whop_product_name', None)

            save_tiers_config(tiers)

            # Also update database record
            sync_tier_to_database(tier_key, tier)

            flash(f'Subscription tier "{tier["name"]}" updated successfully', 'success')
            return redirect(url_for('subscription_tiers.manage_tiers'))

        except Exception as e:
            flash(f'Error updating tier: {str(e)}', 'error')
            logger.error(f"Error updating tier {tier_key}: {str(e)}")
            return redirect(url_for('subscription_tiers.edit_tier', tier_key=tier_key))

    # GET request - show form
    tier = tiers[tier_key]  # Define tier variable for GET requests
    all_permissions = Permission.query.filter_by(is_active=True).all()
    # Group permissions by category for better display
    permissions_by_category = {}
    for perm in all_permissions:
        category = perm.category if perm.category else 'Uncategorized'
        if category not in permissions_by_category:
            permissions_by_category[category] = []
        permissions_by_category[category].append(perm)
    
    # Sort categories and permissions within categories
    sorted_categories = sorted(permissions_by_category.keys())
    for category in sorted_categories:
        permissions_by_category[category].sort(key=lambda p: p.name)

    return render_template('developer/edit_tier.html', 
                         tier_key=tier_key,
                         tier=tier,
                         all_permissions=all_permissions,
                         permissions_by_category=permissions_by_category,
                         sorted_categories=sorted_categories)

@subscription_tiers_bp.route('/delete/<tier_key>', methods=['POST'])
@login_required
def delete_tier(tier_key):
    """Delete a subscription tier"""
    if not current_user.is_developer:
        flash('Developer access required', 'error')
        return redirect(url_for('app_routes.dashboard')) # Assuming 'app_routes' is the blueprint name for dashboard

    tiers = load_tiers_config()

    if tier_key not in tiers:
        flash('Tier not found', 'error')
        return redirect(url_for('subscription_tiers.manage_tiers'))

    # Only prevent deletion of exempt tier (system dependency)
    if tier_key == 'exempt':
        flash(f'Cannot delete "{tier_key}" tier - it is required for system operation', 'error')
        return redirect(url_for('subscription_tiers.manage_tiers'))

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
        return redirect(url_for('subscription_tiers.manage_tiers'))

    tier_name = tiers[tier_key]['name']
    del tiers[tier_key]
    save_tiers_config(tiers)

    # Also remove from database
    tier_record = SubscriptionTier.query.filter_by(key=tier_key).first()
    if tier_record:
        db.session.delete(tier_record)
        db.session.commit()

    flash(f'Subscription tier "{tier_name}" deleted successfully', 'success')
    return redirect(url_for('subscription_tiers.manage_tiers'))

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

    if not tier.get('requires_stripe_billing', False):
        return jsonify({'success': True, 'message': f'Stripe billing not enabled for tier {tier_key}', 'tier': tier})

    if not lookup_key:
        return jsonify({'error': 'No Stripe lookup key configured for this tier', 'tier': tier}), 400

    try:
        # Initialize Stripe
        stripe_key = os.environ.get('STRIPE_SECRET_KEY')
        if not stripe_key:
            logger.error("STRIPE_SECRET_KEY not found in environment variables.")
            return jsonify({'error': 'Stripe secret key not configured in secrets'}), 500

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
                logger.warning(f"Stripe lookup key search failed for '{lookup_key}': {str(lookup_error)}")

            # Method 2: If lookup key failed, fall back to name matching (less reliable)
            if not product:
                logger.info(f"Lookup key '{lookup_key}' not found, falling back to name matching for tier '{tier_key}'")
                try:
                    all_products = stripe.Product.list(limit=100, active=True) # Fetch active products

                    # Define potential name variations to match
                    tier_name_variations = [
                        f"BatchTrack {tier_key.title()}",  # e.g., "BatchTrack Solo"
                        f"BatchTrack {tier.get('name', tier_key.title())}", # e.g., "BatchTrack Solo Plan"
                        tier_key.title(),                  # e.g., "Solo"
                        tier.get('name', tier_key.title()) # e.g., "Solo Plan"
                    ]

                    logger.info(f"Searching {len(all_products.data)} Stripe products for matches with tier '{tier_key}'")

                    for p in all_products.data:
                        # Check if product name contains any of the variations
                        for name_variation in tier_name_variations:
                            if name_variation.lower() in p.name.lower():
                                product = p
                                logger.info(f"Found matching product: {p.name} (ID: {p.id}) for variation: '{name_variation}'")
                                break
                        if product: # If a match is found, break the inner loop
                            break # Break the outer loop as well
                except stripe.error.StripeError as product_list_error:
                    logger.error(f"Failed to list Stripe products for name matching: {str(product_list_error)}")
                    # Continue without product if listing fails

            if not product:
                logger.warning(f"No Stripe product found for tier: {tier_key} (lookup key: {lookup_key}). Please ensure the product exists in Stripe.")
                return jsonify({
                    'success': False,
                    'error': f'No Stripe product found for tier: {tier_key} (lookup key: {lookup_key}). Check your Stripe dashboard and ensure the product exists and is active.',
                    'tier': tier,
                    'sync_status': 'product_not_found'
                }), 404

            logger.info(f"Successfully found Stripe product: {product.id} ({product.name})")

        except stripe.error.StripeError as search_error:
            logger.error(f"Stripe API error during product search for lookup key '{lookup_key}': {str(search_error)}")
            return jsonify({
                'success': False,
                'error': f'Stripe API error: {str(search_error)}',
                'tier': tier,
                'sync_status': 'stripe_api_error'
            }), 400
        except Exception as e:
            logger.error(f"Unexpected error during Stripe product search for tier {tier_key}: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'An unexpected error occurred: {str(e)}',
                'tier': tier,
                'sync_status': 'unexpected_error'
            }), 500

        # Get prices for this product
        monthly_price_data = None
        yearly_price_data = None
        monthly_price_id = None
        yearly_price_id = None

        try:
            # Fetch all active prices for the found product
            prices_response = stripe.Price.list(product=product.id, active=True, limit=10)
            
            for price in prices_response.data:
                if price.recurring and price.recurring.interval == 'month':
                    if price.recurring.interval_count == 1: # Standard monthly price
                        monthly_price_data = price
                        monthly_price_id = price.id
                    elif price.recurring.interval_count == 12: # Monthly price for yearly billing
                        yearly_price_data = price
                        yearly_price_id = price.id
                elif price.recurring and price.recurring.interval == 'year': # Direct yearly interval
                    yearly_price_data = price
                    yearly_price_id = price.id

            # Use default_price if available and not already found by specific interval checks
            if product.default_price and not monthly_price_id and not yearly_price_id:
                try:
                    default_price = stripe.Price.retrieve(product.default_price)
                    if default_price.recurring:
                        if default_price.recurring.interval == 'month':
                            monthly_price_data = default_price
                            monthly_price_id = default_price.id
                        elif default_price.recurring.interval == 'year':
                            yearly_price_data = default_price
                            yearly_price_id = default_price.id
                except stripe.error.StripeError as default_price_error:
                    logger.warning(f"Could not retrieve default price {product.default_price} for product {product.id}: {default_price_error}")

            logger.info(f"Found Stripe prices for product {product.id}: Monthly Price ID={monthly_price_id}, Yearly Price ID={yearly_price_id}")

        except stripe.error.StripeError as price_error:
            logger.error(f"Failed to fetch Stripe prices for product {product.id}: {str(price_error)}")
            return jsonify({
                'success': False,
                'error': f'Failed to fetch Stripe prices: {str(price_error)}',
                'tier': tier,
                'sync_status': 'price_fetch_error'
            }), 400
        except Exception as e:
            logger.error(f"Unexpected error fetching Stripe prices for tier {tier_key}: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'An unexpected error occurred while fetching prices: {str(e)}',
                'tier': tier,
                'sync_status': 'unexpected_price_error'
            }), 500

        # Extract features from product metadata or description
        features = []
        if product.metadata.get('features'):
            # Assumes features are comma-separated in metadata
            features = [f.strip() for f in product.metadata['features'].split(',') if f.strip()]
        elif product.description:
            # Fallback: try to extract features from description if metadata is missing
            # This is a simple split, might need more sophisticated parsing if descriptions are complex
            features = [f.strip() for f in product.description.split(',') if f.strip() and len(f.strip()) > 5] # Basic filter

        # Update tier with Stripe data - IMPORTANT: preserve existing stripe_lookup_key
        tier['stripe_features'] = features
        
        # Update prices and price IDs
        tier['stripe_price_monthly'] = f"${monthly_price_data.unit_amount / 100:.0f}" if monthly_price_data else tier.get('fallback_price_monthly', '$0')
        tier['stripe_price_id_monthly'] = monthly_price_id
        
        tier['stripe_price_yearly'] = f"${yearly_price_data.unit_amount / 100:.0f}" if yearly_price_data else tier.get('fallback_price_yearly', '$0')
        tier['stripe_price_id_yearly'] = yearly_price_id
        
        tier['currency'] = monthly_price_data.currency if monthly_price_data else (yearly_price_data.currency if yearly_price_data else tier.get('currency', 'USD'))

        # The stripe_lookup_key is intentionally NOT updated here to preserve manual configurations.
        # It's read from the tier config itself.

        tier['last_synced'] = datetime.now().isoformat()

        # Update pricing snapshots for resilience
        try:
            from app.models.pricing_snapshot import PricingSnapshot # Corrected import path

            # Update/create snapshot for monthly price
            if monthly_price_data:
                PricingSnapshot.update_from_stripe_data(monthly_price_data, product)
                logger.info(f"Updated pricing snapshot for monthly price ID: {monthly_price_id}")

            # Update/create snapshot for yearly price
            if yearly_price_data:
                PricingSnapshot.update_from_stripe_data(yearly_price_data, product)
                logger.info(f"Updated pricing snapshot for yearly price ID: {yearly_price_id}")

            db.session.commit() # Commit snapshot changes
            logger.info(f"Pricing snapshots updated successfully for tier {tier_key}")

        except Exception as snapshot_error:
            # Log warning but don't fail the entire sync operation if snapshots fail
            logger.warning(f"Failed to update pricing snapshots for tier {tier_key}: {str(snapshot_error)}")

        save_tiers_config(tiers)

        # Also update database record with the current tier configuration
        # This ensures the database reflects the latest sync status and fetched prices/features
        sync_tier_to_database(tier_key, tier)

        logger.info(f"Successfully synced tier {tier_key} with Stripe. Preserved lookup key: {lookup_key}")

        return jsonify({
            'success': True,
            'tier': tier,
            'message': f'Successfully synced {tier["name"]} with Stripe. Lookup key "{lookup_key}" preserved.'
        })

    except stripe.error.StripeError as e:
        logger.error(f"Stripe API error during sync for tier {tier_key}: {str(e)}")
        return jsonify({'error': f'Stripe error: {str(e)}', 'sync_status': 'stripe_error'}), 400
    except Exception as e:
        logger.error(f"An unexpected error occurred during sync for tier {tier_key}: {str(e)}")
        return jsonify({'error': f'Sync failed: {str(e)}', 'sync_status': 'unexpected_error'}), 500

@subscription_tiers_bp.route('/api/tiers')
@login_required 
def api_get_tiers():
    """API endpoint to get current tiers configuration"""
    return jsonify(load_tiers_config())

@subscription_tiers_bp.route('/sync-whop/<tier_key>', methods=['POST'])
@login_required
def sync_whop_tier(tier_key):
    """Sync a tier with Whop products - validate product exists and update DB"""
    from datetime import datetime

    tiers = load_tiers_config()

    if tier_key not in tiers:
        return jsonify({'error': 'Tier not found'}), 404

    tier = tiers[tier_key]

    if not tier.get('requires_whop_billing', False):
        return jsonify({'success': True, 'message': f'Whop billing not enabled for tier {tier_key}', 'tier': tier})

    whop_product_key = tier.get('whop_product_key')

    if not whop_product_key:
        return jsonify({'error': 'No Whop product key configured for this tier', 'tier': tier}), 400

    try:
        # Fetch Whop integration configuration from Flask app config
        whop_store_id = current_app.config.get('WHOP_STORE_ID')
        whop_secret = current_app.config.get('WHOP_SECRET_KEY')

        if not whop_store_id or not whop_secret:
            logger.error("WHOP_STORE_ID or WHOP_SECRET_KEY not found in Flask app config.")
            return jsonify({'error': 'Whop integration not configured in secrets', 'tier': tier}), 500

        # In a real implementation, you would make an API call to Whop here to validate the product key.
        # For now, we'll simulate validation and just update the sync timestamp.
        # Example:
        # import requests
        # whop_api_url = f"https://api.whop.com/v2/store/{whop_store_id}/products/{whop_product_key}"
        # headers = {"Authorization": f"Bearer {whop_secret}"}
        # response = requests.get(whop_api_url, headers=headers)
        # if response.status_code == 200:
        #     product_data = response.json()
        #     tier['whop_product_name'] = product_data.get('name', tier.get('whop_product_name', '')) # Update name if available
        # else:
        #     logger.warning(f"Whop API validation failed for product {whop_product_key}: {response.status_code} - {response.text}")
        #     return jsonify({'error': f'Whop product validation failed: {response.status_code}', 'tier': tier}), 400

        # Update tier with sync timestamp and potentially fetched product name
        tier['whop_last_synced'] = datetime.now().isoformat()

        save_tiers_config(tiers)

        # Also update database record
        sync_tier_to_database(tier_key, tier)

        return jsonify({
            'success': True,
            'tier': tier,
            'message': f'Successfully validated Whop configuration for {tier["name"]}. Whop sync timestamp updated.'
        })

    except Exception as e:
        logger.error(f"An error occurred during Whop sync for tier {tier_key}: {str(e)}")
        return jsonify({'error': f'Whop sync failed: {str(e)}', 'tier': tier}), 500

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

@subscription_tiers_bp.route('/api/tiers/by-cycle/<cycle>')
def api_get_tiers_by_cycle(cycle):
    """API endpoint to get tiers by billing cycle"""
    all_tiers = load_tiers_config()
    filtered_tiers = {
        key: tier for key, tier in all_tiers.items() 
        if (tier.get('billing_cycle', 'monthly') == cycle and 
            tier.get('is_customer_facing', True) and 
            tier.get('is_available', True))
    }
    return jsonify(filtered_tiers)