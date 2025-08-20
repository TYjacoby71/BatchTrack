from flask import render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from ...models import db, Batch, Recipe, InventoryItem, BatchTimer, BatchIngredient, BatchContainer, ExtraBatchIngredient, ExtraBatchContainer, InventoryHistory
from datetime import datetime, timedelta
from ...utils import get_setting
from ...utils.timezone_utils import TimezoneUtils
from ...services.batch_service import BatchService, BatchOperationsService, BatchManagementService
from ...services.inventory_adjustment import process_inventory_adjustment
from ...utils.unit_utils import get_global_unit_list
from ...models import Product

from . import batches_bp
from .start_batch import start_batch_bp
from .cancel_batch import cancel_batch_bp
from .add_extra import add_extra_bp
from .finish_batch import finish_batch_bp

import logging
logger = logging.getLogger(__name__)

@batches_bp.route('/api/batch-remaining-details/<int:batch_id>')
@login_required
def get_batch_remaining_details(batch_id):
    """Get detailed remaining inventory for a specific batch"""
    try:
        result, error = BatchService.get_batch_remaining_details(batch_id)
        if error:
            return jsonify({'success': False, 'error': error}), 500
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_batch_remaining_details: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@batches_bp.route('/columns', methods=['POST'])
@login_required
def set_column_visibility():
    """Set column visibility preferences"""
    columns = request.form.getlist('columns')
    session['visible_columns'] = columns
    flash('Column preferences updated')
    return redirect(url_for('batches.list_batches'))

@batches_bp.route('/')
@login_required
def list_batches():
    """List batches with filtering and pagination"""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        in_progress_page = request.args.get('in_progress_page', 1, type=int)
        completed_page = request.args.get('completed_page', 1, type=int)

        # Default columns to show if user has not set preference
        visible_columns = session.get('visible_columns', ['recipe', 'timestamp', 'total_cost', 'product_quantity', 'tags'])

        # Get filters from request args or session
        filters = {
            'status': request.args.get('status') or session.get('batch_filter_status', 'all'),
            'recipe_id': request.args.get('recipe_id') or session.get('batch_filter_recipe'),
            'start': request.args.get('start') or session.get('batch_filter_start'),
            'end': request.args.get('end') or session.get('batch_filter_end'),
            'sort_by': request.args.get('sort_by') or session.get('batch_sort_by', 'date_desc')
        }

        # Store current filters in session
        session.update({
            'batch_filter_status': filters['status'],
            'batch_filter_recipe': filters['recipe_id'],
            'batch_filter_start': filters['start'],
            'batch_filter_end': filters['end'],
            'batch_sort_by': filters['sort_by']
        })

        # Pagination configuration
        pagination_config = {
            'in_progress_page': in_progress_page,
            'completed_page': completed_page,
            'table_per_page': 10,
            'card_per_page': 8
        }

        # Get all batch data using service
        batch_data = BatchManagementService.prepare_batch_list_data(filters, pagination_config)

        return render_template('pages/batches/batches_list.html',
            InventoryItem=InventoryItem,
            TimezoneUtils=TimezoneUtils,
            visible_columns=visible_columns,
            **batch_data)

    except Exception as e:
        logger.error(f"Error in list_batches: {str(e)}")
        flash(f'Error loading batches: {str(e)}', 'error')
        # Assuming there's a route for the dashboard, e.g., 'app_routes.dashboard'
        # If not, you might redirect to a more generic error page or the list itself.
        # For this example, let's assume 'app_routes.dashboard' exists.
        # If 'app_routes' is not imported or defined, this will fail.
        # Replace with a valid redirect if necessary.
        try:
            # Attempt to import app_routes for redirection
            from . import app_routes # Assuming app_routes is another blueprint
            return redirect(url_for('app_routes.dashboard'))
        except ImportError:
            logger.warning("Could not import 'app_routes' to redirect to dashboard. Redirecting to list_batches.")
            return redirect(url_for('batches.list_batches'))


@batches_bp.route('/<batch_identifier>')
@login_required
def view_batch(batch_identifier):
    """View a specific batch"""
    try:
        print(f"DEBUG: view_batch called with batch_identifier: {batch_identifier}")

        batch = BatchService.get_batch_by_identifier(batch_identifier)
        if not batch:
            flash('Batch not found', 'error')
            return redirect(url_for('batches.list_batches'))

        # Validate access
        is_valid, error_msg = BatchService.validate_batch_access(batch, 'view')
        if not is_valid:
            flash(error_msg, 'error')
            return redirect(url_for('batches.list_batches'))

        print(f"DEBUG: Found batch: {batch.label_code}, status: {batch.status}")

        if batch.status == 'in_progress':
            print(f"DEBUG: Redirecting to in_progress view")
            return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch.id))

        # Get navigation data
        nav_data = BatchManagementService.get_batch_navigation_data(batch)

        print(f"DEBUG: Rendering view_batch.html template for {batch.status} batch")
        return render_template('pages/batches/view_batch.html',
            batch=batch,
            current_time=datetime.now(),
            **nav_data)

    except Exception as e:
        print(f"DEBUG: Error in view_batch: {str(e)}")
        flash(f'Error viewing batch: {str(e)}', 'error')
        return redirect(url_for('batches.list_batches'))

@batches_bp.route('/<int:batch_id>/update-notes', methods=['POST'])
@login_required
def update_batch_notes(batch_id):
    """Update batch notes and tags"""
    try:
        data = request.get_json() if request.is_json else request.form
        notes = data.get('notes', '')
        tags = data.get('tags', '')

        success, message = BatchService.update_batch_notes_and_tags(batch_id, notes, tags)

        if request.is_json:
            if success:
                return jsonify({'message': message, 'redirect': url_for('batches.list_batches')})
            else:
                return jsonify({'error': message}), 403 if 'Permission' in message else 500

        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        return redirect(url_for('batches.list_batches'))

    except Exception as e:
        logger.error(f"Error updating batch notes: {str(e)}")
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Error updating batch: {str(e)}', 'error')
        return redirect(url_for('batches.list_batches'))

@batches_bp.route('/in-progress/<batch_identifier>')
@login_required
def view_batch_in_progress(batch_identifier):
    """View batch in progress with full editing capabilities"""
    try:
        if not isinstance(batch_identifier, int):
            batch_identifier = int(batch_identifier)

        print(f"DEBUG: Looking for batch {batch_identifier}")

        batch = BatchService.get_batch_by_identifier(batch_identifier)
        if not batch:
            flash('Batch not found', 'error')
            return redirect(url_for('batches.list_batches'))

        # Validate access for editing
        is_valid, error_msg = BatchService.validate_batch_access(batch, 'edit')
        if not is_valid:
            flash(error_msg, 'error')
            return redirect(url_for('batches.list_batches'))

        if batch.status != 'in_progress':
            flash('This batch is no longer in progress and cannot be edited.', 'warning')
            return redirect(url_for('batches.view_batch', batch_identifier=batch_identifier))

        # Get navigation data
        nav_data = BatchManagementService.get_batch_navigation_data(batch)

        # Get comprehensive batch context data
        context_data = BatchManagementService.get_batch_context_data(batch)

        # Get timers with proper organization scoping
        timers, has_active_timers = BatchService.get_batch_timers(batch.id)

        return render_template('pages/batches/batch_in_progress.html',
            batch=batch,
            timers=timers,
            now=TimezoneUtils.utc_now(),
            has_active_timers=has_active_timers,
            timedelta=timedelta,
            **nav_data,
            **context_data)

    except Exception as e:
        logger.error(f"Error in view_batch_in_progress: {str(e)}")
        flash(f'Error viewing batch: {str(e)}', 'error')
        return redirect(url_for('batches.list_batches'))

@batches_bp.route('/api/available-ingredients/<int:recipe_id>')
@login_required
def get_available_ingredients_for_batch(recipe_id):
    """Get available ingredients for a specific recipe using USCS"""
    try:
        scale = float(request.args.get('scale', 1.0))
        ingredients_data, error = BatchManagementService.get_available_ingredients_for_batch(recipe_id, scale)

        if error:
            return jsonify({'error': error}), 500

        return jsonify({'ingredients': ingredients_data})

    except Exception as e:
        logger.error(f"Error getting available ingredients: {str(e)}")
        return jsonify({'error': str(e)}), 500

@batches_bp.route('/api/start-batch', methods=['POST'])
@login_required
def api_start_batch():
    """API endpoint to start a new batch from plan production page"""
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        product_quantity = data.get('product_quantity')
        user_id = current_user.id

        if not recipe_id or not product_quantity:
            return jsonify({'success': False, 'message': 'Recipe ID and product quantity are required.'}), 400

        batch_id, success, message = BatchOperationsService.start_batch(recipe_id, product_quantity, user_id)

        if success:
            return jsonify({'success': True, 'message': message, 'batch_id': batch_id})
        else:
            return jsonify({'success': False, 'message': message}), 500

    except Exception as e:
        logger.error(f"Error starting batch via API: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Register sub-blueprints
batches_bp.register_blueprint(start_batch_bp, url_prefix='/batches')
batches_bp.register_blueprint(cancel_batch_bp, url_prefix='/batches')
batches_bp.register_blueprint(add_extra_bp, url_prefix='/add-extra')
batches_bp.register_blueprint(finish_batch_bp, url_prefix='/finish-batch')