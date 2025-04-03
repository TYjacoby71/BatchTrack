
from flask import Blueprint, render_template, request, redirect, flash
from app.routes.utils import load_data, save_data

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings')
def settings():
    data = load_data()
    settings = data.get('settings', {})
    return render_template('settings.html', settings=settings)

@settings_bp.route('/settings/save', methods=['POST'])
def save_settings():
    data = load_data()
    data.setdefault('settings', {})
    data['settings']['expiry_alert_days'] = int(request.form.get('expiry_alert_days', 30))
    save_data(data)
    flash('Settings updated successfully')
    return redirect('/settings')
