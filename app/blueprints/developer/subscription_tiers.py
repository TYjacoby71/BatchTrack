
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
    if os.path.exists(TIERS_CONFIG_FILE):
        with open(TIERS_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        'solo': {
            'name': 'Solo Plan',
            'permissions': ['dashboard.view', 'batches.view', 'batches.create'],
            'features': ['Up to 5 users', 'Full batch tracking', 'Email support'],
            'stripe_price_id': '',
            'stripe_yearly_price_id': '',
            'user_limit': 5,
            'price_display': '$29',
            'price_yearly_display': '$290'
        },
        'team': {
            'name': 'Team Plan', 
            'permissions': ['dashboard.view', 'batches.view', 'batches.create', 'organization.manage_users'],
            'features': ['Up to 10 users', 'Advanced features', 'Custom roles'],
            'stripe_price_id': '',
            'stripe_yearly_price_id': '',
            'user_limit': 10,
            'price_display': '$79',
            'price_yearly_display': '$790'
        },
        'enterprise': {
            'name': 'Enterprise Plan',
            'permissions': ['dashboard.view', 'batches.view', 'batches.create', 'organization.manage_users', 'api.access'],
            'features': ['Unlimited users', 'All features', 'API access'],
            'stripe_price_id': '',
            'stripe_yearly_price_id': '',
            'user_limit': -1,
            'price_display': '$199',
            'price_yearly_display': '$1990'
        }
    }

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
        features = [f.strip() for f in request.form.get('features', '').split('\n') if f.strip()]
        
        new_tier = {
            'name': tier_name,
            'permissions': permissions,
            'features': features,
            'stripe_price_id': request.form.get('stripe_price_id', ''),
            'stripe_yearly_price_id': request.form.get('stripe_yearly_price_id', ''),
            'user_limit': int(request.form.get('user_limit', 1)),
            'price_display': request.form.get('price_display', '$0'),
            'price_yearly_display': request.form.get('price_yearly_display', '$0')
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
        tier['permissions'] = request.form.getlist('permissions')
        tier['features'] = [f.strip() for f in request.form.get('features', '').split('\n') if f.strip()]
        tier['stripe_price_id'] = request.form.get('stripe_price_id', '')
        tier['stripe_yearly_price_id'] = request.form.get('stripe_yearly_price_id', '')
        tier['user_limit'] = int(request.form.get('user_limit', 1))
        tier['price_display'] = request.form.get('price_display', '$0')
        tier['price_yearly_display'] = request.form.get('price_yearly_display', '$0')
        
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
    tiers = load_tiers_config()
    
    if tier_key not in tiers:
        flash('Tier not found', 'error')
        return redirect(url_for('developer.subscription_tiers.manage_tiers'))
    
    tier_name = tiers[tier_key]['name']
    del tiers[tier_key]
    save_tiers_config(tiers)
    
    flash(f'Subscription tier "{tier_name}" deleted successfully', 'success')
    return redirect(url_for('developer.subscription_tiers.manage_tiers'))

@subscription_tiers_bp.route('/api/tiers')
@login_required 
def api_get_tiers():
    """API endpoint to get current tiers configuration"""
    return jsonify(load_tiers_config())
