
from flask import Blueprint, render_template

legal_bp = Blueprint('legal', __name__, url_prefix='/legal')

@legal_bp.route('/privacy')
def privacy_policy():
    """Privacy policy page"""
    return render_template('legal/privacy_policy.html', show_public_header=True)

@legal_bp.route('/terms')
def terms_of_service():
    """Terms of service page"""
    return render_template('legal/terms_of_service.html', show_public_header=True)

@legal_bp.route('/cookies')
def cookie_policy():
    """Cookie policy page"""
    return render_template('legal/cookie_policy.html', show_public_header=True)
