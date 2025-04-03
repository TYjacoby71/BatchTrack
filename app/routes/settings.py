
from flask import Blueprint, render_template, request, redirect, flash
from app.routes.utils import load_data, save_data

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings')
def settings():
    data = load_data()
    settings = data.get('settings', {})
    ingredients = data.get('ingredients', [])
    return render_template('settings.html', settings=settings, ingredients=ingredients)

@settings_bp.route('/settings/save', methods=['POST'])
def save_settings():
    try:
        data = load_data()
        data.setdefault('settings', {})
        expiry_days = int(request.form.get('expiry_alert_days', 30))
        if expiry_days < 1:
            flash('Alert days must be at least 1', 'error')
            return redirect('/settings')
            
        data['settings']['expiry_alert_days'] = expiry_days
        save_data(data)
        flash('Settings updated successfully', 'success')
    except ValueError:
        flash('Invalid value for alert days', 'error')
    except Exception as e:
        flash(f'Error saving settings: {str(e)}', 'error')
    
    return redirect('/settings')

@settings_bp.route('/settings/stock-alerts', methods=['POST'])
def save_stock_alerts():
    try:
        data = load_data()
        for ingredient in data.get('ingredients', []):
            threshold_key = f"threshold_{ingredient['name']}"
            if threshold_key in request.form:
                threshold = request.form[threshold_key]
                if threshold.strip():
                    ingredient['low_stock_threshold'] = float(threshold)
                else:
                    ingredient.pop('low_stock_threshold', None)
        
        save_data(data)
        flash('Stock alert thresholds updated successfully', 'success')
    except ValueError:
        flash('Invalid threshold value provided', 'error')
    except Exception as e:
        flash(f'Error saving stock alerts: {str(e)}', 'error')
    
    return redirect('/settings')
