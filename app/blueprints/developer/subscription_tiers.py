
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, Permission
from app.extensions import db
import json
import os

subscription_tiers_bp = Blueprint('subscription_tiers', __name__, url_prefix='/subscription-tiers')

# Load/save tier configuration
TIERS_CONFIG_FILE = 'subscription_tiers.json'

def load_tiers_config():
    """Load subscription tiers from JSON file"""
    # Default system tiers
    default_tiers = {
        'free': {
            'name': 'Free Plan',
            'feature_groups': ['dashboard', 'inventory'],
            'stripe_lookup_key': '',
            'user_limit': 1,
            'fallback_features': ['Basic features', '1 user only', 'Community support'],
            'stripe_features': [],
            'stripe_price_monthly': 'Free',
            'stripe_price_yearly': 'Free',
            'last_synced': None
        },
        'solo': {
            'name': 'Solo Plan',
            'feature_groups': ['dashboard', 'inventory', 'batches'],
            'stripe_lookup_key': 'solo-plan',
            'user_limit': 1,
            'fallback_features': ['Up to 1 user', 'Full batch tracking', 'Email support'],
            'stripe_features': [],
            'stripe_price_monthly': None,
            'stripe_price_yearly': None,
            'last_synced': None
        },
        'team': {
            'name': 'Team Plan', 
            'feature_groups': ['dashboard', 'inventory', 'batches', 'products', 'user_management'],
            'stripe_lookup_key': 'team-plan',
            'user_limit': 10,
            'fallback_features': ['Up to 10 users', 'Advanced features', 'Custom roles'],
            'stripe_features': [],
            'stripe_price_monthly': None,
            'stripe_price_yearly': None,
            'last_synced': None
        },
        'enterprise': {
            'name': 'Enterprise Plan',
            'feature_groups': ['dashboard', 'inventory', 'batches', 'products', 'user_management', 'api_access', 'advanced_features'],
            'stripe_lookup_key': 'enterprise-plan',
            'user_limit': -1,
            'fallback_features': ['Unlimited users', 'All features', 'API access'],
            'stripe_features': [],
            'stripe_price_monthly': None,
            'stripe_price_yearly': None,
            'last_synced': None
        },
        'exempt': {
            'name': 'Exempt Plan',
            'feature_groups': ['dashboard', 'inventory', 'batches', 'products', 'user_management', 'api_access', 'advanced_features', 'developer_access'],
            'stripe_lookup_key': '',
            'user_limit': -1,
            'fallback_features': ['Unlimited users', 'All features', 'Developer access', 'No billing required'],
            'stripe_features': [],
            'stripe_price_monthly': 'Exempt',
            'stripe_price_yearly': 'Exempt',
            'last_synced': None
        }
    }
    
    if os.path.exists(TIERS_CONFIG_FILE):
        with open(TIERS_CONFIG_FILE, 'r') as f:
            loaded_tiers = json.load(f)
            # Merge with default tiers, keeping any customizations
            for tier_key, tier_data in default_tiers.items():
                if tier_key not in loaded_tiers:
                    loaded_tiers[tier_key] = tier_data
            return loaded_tiers
    
    return default_tiers

def save_tiers_config(tiers):
    """Save subscription tiers to JSON file"""
    with open(TIERS_CONFIG_FILE, 'w') as f:
        json.dump(tiers, f, indent=2)

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
        if user_limit == -1 and tier_key != 'exempt':
            user_limit = 1
        
        new_tier = {
            'name': tier_name,
            'permissions': permissions,
            'stripe_lookup_key': request.form.get('stripe_lookup_key', ''),
            'user_limit': user_limit,
            'fallback_features': fallback_features,
            'stripe_features': [],
            'stripe_price_monthly': None,
            'stripe_price_yearly': None,
            'last_synced': None
        }
        
        tiers[tier_key] = new_tier
        save_tiers_config(tiers)
        
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
        
        # Update tier data
        tier['name'] = request.form.get('tier_name', tier['name'])
        tier['feature_groups'] = request.form.getlist('feature_groups')
        tier['stripe_lookup_key'] = request.form.get('stripe_lookup_key', '')
        
        user_limit = int(request.form.get('user_limit', 1))
        # Only exempt tier can have unlimited users (-1)
        if user_limit == -1 and tier_key != 'exempt':
            user_limit = 1
        tier['user_limit'] = user_limit
        
        tier['fallback_features'] = [f.strip() for f in request.form.get('fallback_features', '').split('\n') if f.strip()]
        
        save_tiers_config(tiers)
        
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
    
    flash(f'Subscription tier "{tier_name}" deleted successfully', 'success')
    return redirect(url_for('developer.subscription_tiers.manage_tiers'))

@subscription_tiers_bp.route('/sync/<tier_key>', methods=['POST'])
@login_required
def sync_tier(tier_key):
    """Sync a tier with Stripe pricing and features"""
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
        
        # Find products by lookup key
        products = stripe.Product.list(lookup_keys=[lookup_key], limit=1)
        
        if not products.data:
            return jsonify({'error': f'No Stripe product found with lookup key: {lookup_key}'}), 404
        
        product = products.data[0]
        
        # Get prices for this product
        prices = stripe.Price.list(product=product.id)
        
        monthly_price = None
        yearly_price = None
        
        for price in prices.data:
            if price.recurring and price.recurring.interval == 'month':
                monthly_price = f"${price.unit_amount // 100}"
            elif price.recurring and price.recurring.interval == 'year':
                yearly_price = f"${price.unit_amount // 100}"
        
        # Get features from product metadata
        features = []
        if product.metadata.get('features'):
            features = [f.strip() for f in product.metadata['features'].split(',')]
        
        # Update tier with Stripe data
        tier['stripe_features'] = features
        tier['stripe_price_monthly'] = monthly_price
        tier['stripe_price_yearly'] = yearly_price
        tier['last_synced'] = datetime.now().isoformat()
        
        save_tiers_config(tiers)
        
        return jsonify({
            'success': True,
            'tier': tier,
            'message': f'Successfully synced {tier["name"]} with Stripe'
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
