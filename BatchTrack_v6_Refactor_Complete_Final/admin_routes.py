
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required
from models import db, InventoryUnit, ProductUnit

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/units')
@login_required
def unit_manager():
    inventory_units = InventoryUnit.query.all()
    product_units = ProductUnit.query.all()
    return render_template('unit_manager.html', inventory_units=inventory_units, product_units=product_units)

@admin_bp.route('/admin/units/add/inventory', methods=['POST'])
@login_required
def add_inventory_unit():
    name = request.form.get('name')
    utype = request.form.get('type')
    base_equiv = request.form.get('base_equivalent', type=float)
    aliases = request.form.get('aliases')
    density = 'density_required' in request.form
    db.session.add(InventoryUnit(name=name, type=utype, base_equivalent=base_equiv, aliases=aliases, density_required=density))
    db.session.commit()
    return redirect(url_for('admin.unit_manager'))

@admin_bp.route('/admin/units/add/product', methods=['POST'])
@login_required
def add_product_unit():
    name = request.form.get('name')
    db.session.add(ProductUnit(name=name))
    db.session.commit()
    return redirect(url_for('admin.unit_manager'))
