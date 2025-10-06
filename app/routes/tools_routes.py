from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from app.services.unit_conversion.unit_conversion import ConversionEngine
from app.models import GlobalItem

# Public Tools blueprint
# Mounted at /tools via blueprints_registry

tools_bp = Blueprint('tools_bp', __name__)

@tools_bp.route('/')
def tools_index():
    """Public tools landing. Embeds calculators with progressive disclosure.
    Includes: Unit Converter, Fragrance Load Calculator, Lye Calculator (view-only),
    and quick draft Recipe Tool (category-aware) with Save CTA that invites sign-in.
    """
    return render_template('tools/index.html')

@tools_bp.route('/soap')
def tools_soap():
    return render_template('tools/soap.html')

@tools_bp.route('/candles')
def tools_candles():
    return render_template('tools/candles.html')

@tools_bp.route('/lotions')
def tools_lotions():
    return render_template('tools/lotions.html')

@tools_bp.route('/herbal')
def tools_herbal():
    return render_template('tools/herbal.html')

@tools_bp.route('/baker')
def tools_baker():
    return render_template('tools/baker.html')


@tools_bp.route('/draft', methods=['POST'])
def tools_draft():
    """Accept a draft from the public tools page and redirect to sign-in/save flow.
    The draft payload is stored in session via query string for now (MVP), then the
    /recipes/new page will read and prefill when user is authenticated.
    """
    from flask import session
    data = request.get_json() or {}
    session['tool_draft'] = data
    session.permanent = True
    # Redirect to sign-in or directly to recipes new if already logged in
    return jsonify({'success': True, 'redirect': url_for('recipes.new_recipe')})
