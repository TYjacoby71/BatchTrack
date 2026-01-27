from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.extensions import db
from app.models.addon import Addon
from app.utils.permissions import require_permission


addons_bp = Blueprint('addons', __name__, url_prefix='/addons')


@addons_bp.route('/')
@login_required
@require_permission('dev.manage_tiers')
def list_addons():
    addons = Addon.query.order_by(Addon.name).all()
    return render_template('developer/addons/list.html', addons=addons)


@addons_bp.route('/create', methods=['GET', 'POST'])
@login_required
@require_permission('dev.manage_tiers')
def create_addon():
    if request.method == 'POST':
        key = (request.form.get('key') or '').strip()
        name = (request.form.get('name') or '').strip()
        description = request.form.get('description')
        permission_name = (request.form.get('permission_name') or '').strip() or None
        function_key = (request.form.get('function_key') or '').strip() or None
        billing_type = (request.form.get('billing_type') or 'subscription').strip()
        stripe_lookup_key = (request.form.get('stripe_lookup_key') or '').strip() or None
        # retention_extension_days deprecated for retention feature
        is_active = True if request.form.get('is_active') == 'on' else False

        if not key:
            flash('Key is required', 'error')
            return redirect(url_for('developer.addons.create_addon'))
        if not name:
            flash('Name is required', 'error')
            return redirect(url_for('developer.addons.create_addon'))

        if Addon.query.filter_by(key=key).first():
            flash('Addon key already exists', 'error')
            return redirect(url_for('developer.addons.create_addon'))

        addon = Addon(
            key=key,
            name=name,
            description=description,
            permission_name=permission_name,
            function_key=function_key,
            billing_type=billing_type,
            stripe_lookup_key=stripe_lookup_key,
            
            is_active=is_active
        )
        db.session.add(addon)
        db.session.commit()
        flash('Add-on created', 'success')
        return redirect(url_for('developer.addons.list_addons'))

    return render_template('developer/addons/create.html')


@addons_bp.route('/edit/<int:addon_id>', methods=['GET', 'POST'])
@login_required
@require_permission('dev.manage_tiers')
def edit_addon(addon_id):
    addon = db.session.get(Addon, addon_id)
    if not addon:
        flash('Add-on not found', 'error')
        return redirect(url_for('developer.addons.list_addons'))

    if request.method == 'POST':
        addon.name = (request.form.get('name') or addon.name).strip()
        addon.description = request.form.get('description')
        addon.permission_name = (request.form.get('permission_name') or '').strip() or None
        addon.function_key = (request.form.get('function_key') or '').strip() or None
        addon.billing_type = (request.form.get('billing_type') or addon.billing_type).strip()
        addon.stripe_lookup_key = (request.form.get('stripe_lookup_key') or '').strip() or None
        # retention_extension_days deprecated for retention feature
        addon.is_active = True if request.form.get('is_active') == 'on' else False

        db.session.commit()
        flash('Add-on updated', 'success')
        return redirect(url_for('developer.addons.list_addons'))

    return render_template('developer/addons/edit.html', addon=addon)


@addons_bp.route('/delete/<int:addon_id>', methods=['POST'])
@login_required
@require_permission('dev.manage_tiers')
def delete_addon(addon_id):
    addon = db.session.get(Addon, addon_id)
    if not addon:
        flash('Add-on not found', 'error')
        return redirect(url_for('developer.addons.list_addons'))

    db.session.delete(addon)
    db.session.commit()
    flash('Add-on deleted', 'success')
    return redirect(url_for('developer.addons.list_addons'))

