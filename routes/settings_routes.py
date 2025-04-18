
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, InventoryUnit, ProductUnit
import json

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings')
@login_required
def settings():
    inventory_units = InventoryUnit.query.all()
    product_units = ProductUnit.query.all()
    try:
        with open("settings.json", "r") as f:
            settings_data = json.load(f)
    except:
        settings_data = {"enable_debug": False, "show_experimental": False}
    
    return render_template('settings.html', 
                         inventory_units=inventory_units,
                         product_units=product_units,
                         settings=settings_data)

@settings_bp.route('/settings/units', methods=['POST'])
@login_required
def manage_units():
    unit_type = request.form.get('type')
    name = request.form.get('name')
    if unit_type == 'inventory':
        unit = InventoryUnit(name=name)
    else:
        unit = ProductUnit(name=name)
    db.session.add(unit)
    db.session.commit()
    flash('Unit added successfully')
    return redirect(url_for('settings.settings'))
