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
    tier_record.name = tier_config.get('name', tier_key.title())
    tier_record.description = tier_config.get('description', '')
    tier_record.user_limit = tier_config.get('user_limit', 1)
    tier_record.is_customer_facing = tier_config.get('is_customer_facing', True)
    tier_record.is_available = tier_config.get('is_available', True)
    tier_record.requires_stripe_billing = tier_config.get('requires_stripe_billing', True)
    tier_record.requires_whop_billing = tier_config.get('requires_whop_billing', False)

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
        
        new_tier = {
            'name': tier_name,
            'permissions': permissions,
            'feature_groups': request.form.getlist('feature_groups'),
            'stripe_lookup_key': request.form.get('stripe_lookup_key', ''),
            'user_limit': user_limit,
            'is_customer_facing': request.form.get('is_customer_facing') == 'on',
            'is_available': request.form.get('is_available') == 'on',
            'pricing_category': request.form.get('pricing_category', 'monthly'),
            'fallback_features': fallback_features,
            'fallback_price': request.form.get('fallback_price', '$0'),
            'stripe_features': [],
            'stripe_price': None,
            'stripe_price_id': None,
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
        tier['requires_stripe_billing'] = 'requires_stripe_billing' in request.form

        # Pricing configuration (simplified - Stripe handles billing cycle, price, currency)
        tier['pricing_category'] = request.form.get('pricing_category', 'monthly')

        # Payment provider settings - simplified
        tier['supports_whop'] = 'supports_whop' in request.form

        tier['permissions'] = request.form.getlist('permissions')
        tier['feature_groups'] = request.form.getlist('feature_groups')
        tier['stripe_lookup_key'] = request.form.get('stripe_lookup_key', '')
        tier['whop_product_key'] = request.form.get('whop_product_key', '')
        tier['whop_product_name'] = request.form.get('whop_product_name', '')

        user_limit_str = request.form.get('user_limit', '1')
        try:
            user_limit = int(user_limit_str)
        except (ValueError, TypeError):
            user_limit = 1  # Default fallback

        tier['user_limit'] = user_limit

        # Update visibility controls
        tier['is_customer_facing'] = request.form.get('is_customer_facing') == 'on'
        tier['is_available'] = request.form.get('is_available') == 'on'
        tier['requires_stripe_billing'] = request.form.get('requires_stripe_billing') == 'on'

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

    tier = tiers[tier_key]
    stripe_lookup_key = tier.get('stripe_lookup_key')
    
    try:
        # Sync the tier configuration to database
        sync_tier_to_database(tier_key, tier)
        
        # If tier has Stripe lookup key, fetch pricing from Stripe
        if stripe_lookup_key:
            try:
                from app.services.stripe_service import StripeService
                pricing_data = StripeService.get_stripe_pricing_for_lookup_key(stripe_lookup_key)
                
                if pricing_data:
                    # Update the tier config with fresh pricing data
                    tier['stripe_price'] = pricing_data.get('formatted_price', tier.get('fallback_price', '$0'))
                    tier['stripe_price_id'] = pricing_data.get('price_id')
                    tier['billing_cycle'] = pricing_data.get('billing_cycle', 'monthly')
                    tier['last_synced'] = pricing_data.get('last_synced')
                    
                    # Save updated pricing back to JSON
                    save_tiers_config(tiers)
                    
                    logger.info(f"Synced tier {tier_key} with Stripe pricing: {tier['stripe_price']}")
                else:
                    logger.warning(f"No Stripe pricing found for lookup key: {stripe_lookup_key}")
                    
            except Exception as stripe_error:
                logger.error(f"Failed to fetch Stripe pricing for {tier_key}: {str(stripe_error)}")
                # Continue without Stripe pricing - fallback to config values
        
        return jsonify({
            'success': True,
            'tier': tier,
            'message': f'Successfully synced {tier["name"]} configuration' + 
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