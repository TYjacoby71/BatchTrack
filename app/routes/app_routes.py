from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
from app.models import Recipe, InventoryItem, Batch
from flask_login import login_required, current_user
from app.utils.permissions import require_permission, get_effective_organization_id, permission_required, any_permission_required
from app.services.combined_inventory_alerts import CombinedInventoryAlertService
from app.blueprints.expiration.services import ExpirationService
from app.services.statistics import AnalyticsDataService
from app.extensions import limiter
import logging

logger = logging.getLogger(__name__)

app_routes_bp = Blueprint('app_routes', __name__)

# Dashboard no longer performs stock checks - this is handled by production planning

@app_routes_bp.route('/dashboard')
@app_routes_bp.route('/user_dashboard')
@limiter.limit("5000 per 1 minute")
@login_required
def dashboard():
    """Main dashboard view with stock checking and alerts"""
    force_refresh = (request.args.get('refresh') or '').lower() in ('1', 'true', 'yes')
    # Developer users should only access this dashboard when viewing an organization
    if current_user.user_type == 'developer':
        selected_org_id = session.get('dev_selected_org_id')
        if not selected_org_id:
            flash('Developers must select an organization to view customer dashboard', 'warning')
            return redirect(url_for('developer.dashboard'))

        # Verify the organization still exists
        from app.models import Organization
        from ..extensions import db

        try:
            selected_org = db.session.get(Organization, selected_org_id)
            if not selected_org:
                session.pop('dev_selected_org_id', None)
                session.pop('dev_masquerade_context', None)
                flash('Selected organization no longer exists. Masquerade cleared.', 'error')
                return redirect(url_for('developer.dashboard'))
        except Exception as org_error:
            print("---!!! ORGANIZATION QUERY ERROR (ORIGINAL SIN?) !!!---")
            print(f"Error: {org_error}")
            print("----------------------------------------------------")
            db.session.rollback()
            flash('Database error accessing organization. Please try again.', 'error')
            return redirect(url_for('developer.dashboard'))

    from ..extensions import db

    # Initialize with safe defaults
    recipes = []
    active_batch = None
    alert_data = {'alerts': [], 'total_alerts': 0, 'hidden_count': 0}
    low_stock_ingredients = []
    expiration_summary = {'expired_fifo': 0, 'expiring_fifo': 0, 'expired_products': 0, 'expiring_products': 0}

    try:
        # Force clean state
        db.session.rollback()

        # Get recipes with explicit error catching
        try:
            recipes_query = Recipe.query
            if current_user.organization_id:
                recipes_query = recipes_query.filter_by(organization_id=current_user.organization_id)
            recipes = recipes_query.all()
        except Exception as recipe_error:
            logger.warning(f"Recipe query error: {recipe_error}")
            db.session.rollback()
            recipes = []

        # Get active batch with explicit error catching
        try:
            batch_query = Batch.query.filter_by(status='in_progress')
            if current_user.organization_id:
                batch_query = batch_query.filter_by(organization_id=current_user.organization_id)
            active_batch = batch_query.first()
        except Exception as batch_error:
            print("---!!! BATCH QUERY ERROR (ORIGINAL SIN?) !!!---")
            print(f"Error: {batch_error}")
            print("-----------------------------------------------")
            db.session.rollback()
            active_batch = None

        # Get dashboard alerts with explicit error catching
        try:
            dismissed_alerts = session.get('dismissed_alerts', [])
            alert_data = AnalyticsDataService.get_dashboard_alerts(
                max_alerts=3,
                dismissed_alerts=dismissed_alerts,
                force_refresh=force_refresh,
            )
        except Exception as alert_error:
            print("---!!! DASHBOARD ALERTS ERROR (ORIGINAL SIN?) !!!---")
            print(f"Error: {alert_error}")
            print("----------------------------------------------------")
            db.session.rollback()
            alert_data = {'alerts': [], 'total_alerts': 0, 'hidden_count': 0}

        # Get inventory alerts with explicit error catching
        try:
            low_stock_ingredients = CombinedInventoryAlertService.get_low_stock_ingredients()
        except Exception as inv_error:
            print("---!!! INVENTORY ALERTS ERROR (ORIGINAL SIN?) !!!---")
            print(f"Error: {inv_error}")
            print("----------------------------------------------------")
            db.session.rollback()
            low_stock_ingredients = []

        # Get expiration summary with explicit error catching
        try:
            expiration_summary = ExpirationService.get_expiration_summary()
        except Exception as exp_error:
            print("---!!! EXPIRATION SERVICE ERROR (ORIGINAL SIN?) !!!---")
            print(f"Error: {exp_error}")
            print("------------------------------------------------------")
            db.session.rollback()
            expiration_summary = {'expired_fifo': 0, 'expiring_fifo': 0, 'expired_products': 0, 'expiring_products': 0}

    except Exception as e:
        print("---!!! GENERAL DASHBOARD ERROR !!!---")
        print(f"Error: {e}")
        print("------------------------------------")
        db.session.rollback()
        flash('Dashboard temporarily unavailable. Please try refreshing the page.', 'error')

    return render_template("dashboard.html",
                         recipes=recipes,
                         active_batch=active_batch,
                         current_user=current_user,
                         alert_data=alert_data,
                         low_stock_ingredients=low_stock_ingredients,
                         expiration_summary=expiration_summary)


@app_routes_bp.route('/unit-manager')
@login_required
@permission_required('manage_units')
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
        from app.services.statistics import AnalyticsDataService

        force_refresh = (request.args.get('refresh') or '').lower() in ('1', 'true', 'yes')
        alert_data = AnalyticsDataService.get_dashboard_alerts(
            dismissed_alerts=dismissed_alerts,
            max_alerts=3,
            force_refresh=force_refresh,
        )
        return jsonify(alert_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app_routes_bp.route('/auth-check', methods=['GET'])
@login_required
def auth_check():
    """Lightweight endpoint to verify authentication status without heavy DB work."""
    return jsonify({'status': 'ok'})


@app_routes_bp.route('/fault-log')
@login_required
@permission_required('view_fault_log')
def view_fault_log():
    try:
        force_refresh = (request.args.get('refresh') or '').lower() in ('1', 'true', 'yes')
        if current_user.user_type == 'developer':
            selected_org_id = session.get('dev_selected_org_id')
            if selected_org_id:
                faults = AnalyticsDataService.get_fault_log_entries(
                    organization_id=selected_org_id,
                    include_all=False,
                    force_refresh=force_refresh,
                )
            else:
                faults = AnalyticsDataService.get_fault_log_entries(
                    include_all=True,
                    force_refresh=force_refresh,
                )
        elif current_user.organization_id:
            faults = AnalyticsDataService.get_fault_log_entries(
                organization_id=current_user.organization_id,
                include_all=False,
                force_refresh=force_refresh,
            )
        else:
            faults = []

        return render_template('fault_log.html', faults=faults)
    except Exception as e:
        flash(f'Error loading fault log: {str(e)}', 'error')
        return render_template('fault_log.html', faults=[])

@app_routes_bp.route('/api/server-time')
@app_routes_bp.route('/api/timer-summary')
@limiter.limit("5000 per 1 minute")
def get_server_time():
    """Get current server time in UTC and user's timezone, also auto-complete expired timers"""
    from flask_login import current_user
    from app.utils.timezone_utils import TimezoneUtils
    from app.services.timer_service import TimerService

    # Auto-complete expired timers on each server time request
    # This provides a lightweight way to keep timers updated
    try:
        TimerService.complete_expired_timers()
    except Exception as e:
        # Don't let timer errors break the time endpoint
        print(f"Timer auto-completion error: {e}")

    server_utc = TimezoneUtils.utc_now()

    def _iso(dt):
        aware = TimezoneUtils.ensure_timezone_aware(dt)
        return aware.isoformat(timespec='seconds')

    # If user is logged in, also provide their local time
    user_time = None
    if current_user and current_user.is_authenticated:
        user_timezone = getattr(current_user, 'timezone', 'UTC')
        try:
            user_time = TimezoneUtils.convert_to_timezone(server_utc, user_timezone)
        except Exception:
            user_time = server_utc  # Fallback to UTC if conversion fails

    server_iso = _iso(server_utc)
    user_iso = _iso(user_time) if user_time else server_iso

    return jsonify({
        'server_utc': server_iso,
        'user_time': user_iso,
        'timestamp': server_utc.timestamp()
    })

@app_routes_bp.route('/api/timer-summary')
@login_required
def get_timer_summary():
    """Get active timers summary"""
    try:
        from app.services.timer_service import TimerService
        from app.utils.timezone_utils import TimezoneUtils # Added missing import
        active_timers = TimerService.get_active_timers_for_user(current_user.id)

        return jsonify({
            'active_timers': len(active_timers),
            'timers': [
                {
                    'id': timer.id,
                    'name': timer.name or 'Timer',
                    'remaining_time': max(0, int((timer.end_time - TimezoneUtils.utc_now()).total_seconds())) if timer.end_time else 0
                }
                for timer in active_timers[:5]  # Limit to 5 most recent
            ]
        })
    except Exception as e:
        return jsonify({'active_timers': 0, 'timers': [], 'error': str(e)})