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
from ...services.production_planning.service import PlanProductionService

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

@batches_bp.route('/api/batch-inventory-summary/<int:batch_id>')
@login_required
def get_batch_inventory_summary(batch_id):
    """Get batch inventory summary for FIFO modal"""
    try:
        from ..api.fifo_routes import get_batch_inventory_summary as fifo_summary
        # Call the function directly
        result = fifo_summary(batch_id)
        return result
    except ImportError as e:
        logger.error(f"Failed to import batch inventory summary function: {str(e)}")
        return jsonify({'success': False, 'error': 'Batch inventory summary function not available'}), 500
    except Exception as e:
        logger.error(f"Error in get_batch_inventory_summary: {str(e)}")
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
        # Return empty batch data to prevent template errors
        return render_template('pages/batches/batches_list.html',
            batches=[],
            all_recipes=[],
            in_progress_pagination=None,
            completed_pagination=None,
            InventoryItem=InventoryItem,
            TimezoneUtils=TimezoneUtils,
            visible_columns=['recipe', 'timestamp', 'total_cost', 'product_quantity', 'tags'])


@batches_bp.route('/<batch_identifier>')
@login_required
def view_batch_record(batch_identifier):
    """View a specific batch record - handles completed, failed, and cancelled batches"""
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

        # Redirect in-progress batches to the editable view
        if batch.status == 'in_progress':
            print(f"DEBUG: Redirecting to in_progress view")
            return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch.id))

        # Get navigation data for completed, failed, or cancelled batches
        nav_data = BatchManagementService.get_batch_navigation_data(batch)
        
        # Get comprehensive batch context data (includes freshness_summary)
        context_data = BatchManagementService.get_batch_context_data(batch)

        print(f"DEBUG: Rendering batch record view for {batch.status} batch")
        return render_template('pages/batches/view_batch.html',
            batch=batch,
            current_time=datetime.now(),
            **nav_data,
            **context_data)

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
                return jsonify({'error': message}), 500 if 'Permission' not in message else 403

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
    """View active batch with full editing capabilities"""
    try:
        if not isinstance(batch_identifier, int):
            batch_identifier = int(batch_identifier)

        print(f"DEBUG: Looking for active batch {batch_identifier}")

        batch = BatchService.get_batch_by_identifier(batch_identifier)
        if not batch:
            flash('Batch not found', 'error')
            return redirect(url_for('batches.list_batches'))

        # Validate access for editing
        is_valid, error_msg = BatchService.validate_batch_access(batch, 'edit')
        if not is_valid:
            flash(error_msg, 'error')
            return redirect(url_for('batches.list_batches'))

        # If batch is no longer in progress, redirect to the batch record view
        if batch.status != 'in_progress':
            status_message = {
                'completed': 'This batch has been completed.',
                'failed': 'This batch has failed.',
                'cancelled': 'This batch has been cancelled.'
            }.get(batch.status, 'This batch is no longer active.')

            flash(f'{status_message} Viewing batch record.', 'info')
            return redirect(url_for('batches.view_batch_record', batch_identifier=batch_identifier))

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
    """Start a new batch from a unified PlanSnapshot built server-side."""
    try:
        data = request.get_json() or {}
        recipe_id = data.get('recipe_id')
        if not recipe_id:
            return jsonify({'success': False, 'message': 'Recipe ID is required.'}), 400

        scale = float(data.get('scale', 1.0))
        batch_type = data.get('batch_type', 'ingredient')
        notes = data.get('notes', '')
        containers_data = data.get('containers', []) or []

        # Portioning override captured consistently in the snapshot
        portioning_override = None
        if data.get('is_portioned') in {True, 'true', 'True', 1, '1'}:
            try:
                portioning_override = {
                    'is_portioned': True,
                    'portion_name': data.get('portion_name'),
                    'portion_unit_id': data.get('portion_unit_id'),
                    'portion_count': int(data.get('portion_count')) if data.get('portion_count') not in (None, '') else None
                }
            except Exception:
                portioning_override = {
                    'is_portioned': True,
                    'portion_name': data.get('portion_name'),
                    'portion_unit_id': data.get('portion_unit_id'),
                    'portion_count': None
                }

        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return jsonify({'success': False, 'message': 'Recipe not found.'}), 404

        snapshot_obj = PlanProductionService.build_plan(
            recipe=recipe,
            scale=scale,
            batch_type=batch_type,
            notes=notes,
            containers=containers_data,
            portioning_override=portioning_override
        )
        plan_dict = snapshot_obj.__dict__.copy()
        batch, errors = BatchOperationsService.start_batch(plan_dict)

        if not batch:
            return jsonify({'success': False, 'message': '; '.join(errors) if isinstance(errors, list) else str(errors)}), 400

        message = 'Batch started successfully'
        if errors:
            message = f"Batch started with warnings: {'; '.join(errors)}"

        return jsonify({'success': True, 'message': message, 'batch_id': batch.id})

    except Exception as e:
        logger.error(f"Error starting batch via API: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Register sub-blueprints
batches_bp.register_blueprint(start_batch_bp, url_prefix='/start')
batches_bp.register_blueprint(finish_batch_bp, url_prefix='/finish-batch')
batches_bp.register_blueprint(cancel_batch_bp, url_prefix='')
batches_bp.register_blueprint(add_extra_bp, url_prefix='/add-extra')