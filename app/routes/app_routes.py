from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
from ..models import Recipe, InventoryItem, Batch
from ..services.stock_check import universal_stock_check
from flask_login import login_required, current_user
from ..utils.permissions import require_permission
from ..services.combined_inventory_alerts import CombinedInventoryAlertService
from ..blueprints.expiration.services import ExpirationService
from ..services.dashboard_alerts import DashboardAlertService

app_routes_bp = Blueprint('app_routes', __name__)

# Helper functions for stock checking
def check_stock_for_recipe(recipe, scale=1):
    """Check stock availability for a recipe"""
    try:
        result = universal_stock_check(recipe, scale)
        return result['stock_check'], result['all_ok']
    except Exception as e:
        return [], False

def check_container_availability(container_ids, scale=1):
    """Check container availability - placeholder implementation"""
    # This function needs to be implemented based on your container model
    return [], True

@app_routes_bp.route('/dashboard')
@app_routes_bp.route('/user_dashboard')
@login_required
def dashboard():
    # Developer users should only access this dashboard when viewing an organization
    if current_user.user_type == 'developer' and not session.get('dev_selected_org_id'):
        return redirect(url_for('developer.dashboard'))

    recipes_query = Recipe.query
    if current_user.organization_id:
        recipes_query = recipes_query.filter_by(organization_id=current_user.organization_id)
    recipes = recipes_query.all()

    batch_query = Batch.query.filter_by(status='in_progress')
    if current_user.organization_id:
        batch_query = batch_query.filter_by(organization_id=current_user.organization_id)
    active_batch = batch_query.first()

    # Get unified dashboard alerts with dismissed alerts from session
    dismissed_alerts = session.get('dismissed_alerts', [])
    alert_data = DashboardAlertService.get_dashboard_alerts(
        max_alerts=3, 
        dismissed_alerts=dismissed_alerts
    )

    # Get additional alert data for compatibility
    low_stock_ingredients = CombinedInventoryAlertService.get_low_stock_ingredients()
    expiration_summary = ExpirationService.get_expiration_summary()

    stock_check = None
    selected_recipe = None
    scale = 1
    status = None

    if request.method == "POST":
        recipe_id = request.form.get("recipe_id")
        try:
            scale = float(request.form.get("scale", 1))
            selected_recipe = Recipe.scoped().filter_by(id=recipe_id).first()
            if selected_recipe:
                stock_check, all_ok = check_stock_for_recipe(selected_recipe, scale)
                status = "ok" if all_ok else "bad"
                for item in stock_check:
                    if item["status"] == "LOW" and status != "bad":
                        status = "low"
                        break
        except ValueError as e:
            flash("Invalid scale value")

    return render_template("dashboard.html", 
                         recipes=recipes,
                         stock_check=stock_check,
                         selected_recipe=selected_recipe,
                         scale=scale,
                         status=status,
                         active_batch=active_batch,
                         current_user=current_user,
                         alert_data=alert_data,
                         low_stock_ingredients=low_stock_ingredients,
                         expiration_summary=expiration_summary)

@app_routes_bp.route('/stock/check', methods=['POST'])
@login_required
def check_stock():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        recipe_id = data.get('recipe_id')
        if not recipe_id:
            return jsonify({"error": "Recipe ID is required"}), 400

        try:
            scale = float(data.get('scale', 1.0))
            if scale <= 0:
                return jsonify({"error": "Scale must be greater than 0"}), 400
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid scale value"}), 400

        recipe = Recipe.query.get_or_404(recipe_id)

        # Use universal stock check service
        result = universal_stock_check(recipe, scale)
        stock_check = result['stock_check']
        all_ok = result['all_ok']

        # Handle container validation
        container_ids = data.get('container_ids', [])
        if container_ids and isinstance(container_ids, list):
            container_check, containers_ok = check_container_availability(container_ids, scale)
            stock_check.extend(container_check)
            all_ok = all_ok and containers_ok

        status = "ok" if all_ok else "bad"
        for item in stock_check:
            if item["status"] == "LOW" and status != "bad":
                status = "low"
                break

        # Format the response to match template expectations
        results = [{
            'name': item['name'],
            'needed': item['needed'],
            'available': item['available'],
            'unit': item['unit'],
            'status': item['status'],
            'type': item.get('type', 'ingredient')
        } for item in stock_check]

        return jsonify({
            "stock_check": results,
            "status": status,
            "all_ok": all_ok,
            "recipe_name": recipe.name
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app_routes_bp.route('/unit-manager')
@login_required
def unit_manager():
    return redirect(url_for('conversion.manage_units'))

@app_routes_bp.route('/api/dismiss-alert', methods=['POST'])
@login_required
def dismiss_alert():
    """API endpoint to dismiss alerts for the user session"""
    try:
        data = request.get_json()
        alert_type = data.get('alert_type')

        if not alert_type:
            return jsonify({'error': 'Alert type is required'}), 400

        # Store dismissed alerts in session
        dismissed_alerts = session.get('dismissed_alerts', [])
        if alert_type not in dismissed_alerts:
            dismissed_alerts.append(alert_type)
            session['dismissed_alerts'] = dismissed_alerts
            session.permanent = True

        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app_routes_bp.route('/api/dashboard-alerts')
@login_required
def api_dashboard_alerts():
    """API endpoint to get fresh dashboard alerts"""
    try:
        dismissed_alerts = session.get('dismissed_alerts', [])
        alert_data = DashboardAlertService.get_dashboard_alerts(
            max_alerts=3, 
            dismissed_alerts=dismissed_alerts
        )
        return jsonify(alert_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

from flask import Blueprint
app_routes = Blueprint('app_routes', __name__)

@app_routes.route('/fault-log')
@login_required
def view_fault_log():
    try:
        import json
        import os
        from datetime import datetime
        from flask_login import current_user

        fault_file = 'faults.json'
        faults = []

        if os.path.exists(fault_file):
            with open(fault_file, 'r') as f:
                all_faults = json.load(f)

                # Filter faults by organization unless user is developer
                if current_user.user_type == 'developer':
                    # Developers can see all faults or filtered by selected org
                    from flask import session
                    selected_org_id = session.get('dev_selected_org_id')
                    if selected_org_id:
                        faults = [f for f in all_faults if f.get('organization_id') == selected_org_id]
                    else:
                        faults = all_faults
                elif current_user.organization_id:
                    # Regular users only see their organization's faults
                    faults = [f for f in all_faults if f.get('organization_id') == current_user.organization_id]
                else:
                    faults = []

        # Sort by timestamp, newest first
        faults.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        return render_template('fault_log.html', faults=faults)
    except Exception as e:
        flash(f'Error loading fault log: {str(e)}', 'error')
        return render_template('fault_log.html', faults=[])

@app_routes_bp.route('/api/server-time')
def get_server_time():
    """Get current server time in UTC and user's timezone, also auto-complete expired timers"""
    from flask_login import current_user
    from ..utils.timezone_utils import TimezoneUtils
    from ..services.timer_service import TimerService

    # Auto-complete expired timers on each server time request
    # This provides a lightweight way to keep timers updated
    try:
        TimerService.complete_expired_timers()
    except Exception as e:
        # Don't let timer errors break the time endpoint
        print(f"Timer auto-completion error: {e}")

    server_utc = TimezoneUtils.utc_now()

    # If user is logged in, also provide their local time
    user_time = None
    if current_user and current_user.is_authenticated:
        user_timezone = getattr(current_user, 'timezone', 'UTC')
        try:
            user_time = TimezoneUtils.convert_to_timezone(server_utc, user_timezone)
        except:
            user_time = server_utc  # Fallback to UTC if conversion fails

    return jsonify({
        'server_utc': server_utc.isoformat(),
        'user_time': user_time.isoformat() if user_time else server_utc.isoformat(),
        'timestamp': server_utc.timestamp()
    })