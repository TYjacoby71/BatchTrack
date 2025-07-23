from flask import render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.utils.permissions import require_permission
from . import timers_bp
from ...services.timer_service import TimerService
from ...models import db, Batch

@timers_bp.route('/list_timers')
@timers_bp.route('/timer_list')
@login_required
def list_timers():
    """Display all timers with management interface"""
    timer_summary = TimerService.get_timer_summary()
    active_timers = TimerService.get_active_timers()

    # Get active batches for the dropdown
    query = Batch.query.filter_by(status='in_progress')
    if current_user and current_user.is_authenticated and current_user.organization_id:
        query = query.filter(Batch.organization_id == current_user.organization_id)
    active_batches = query.all()

    return render_template('timer_list.html', 
                         timer_summary=timer_summary,
                         active_timers=active_timers,
                         timers=active_timers,  # For template compatibility
                         active_batches=[{'id': b.id, 'recipe_name': getattr(b.recipe, 'name', 'Unknown Recipe')} for b in active_batches])

@timers_bp.route('/api/create-timer', methods=['POST'])
@timers_bp.route('/create', methods=['POST'])
@login_required
@require_permission('timers.create')
def api_create_timer():
    """Create a new timer for a batch"""
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        batch_id = data.get('batch_id')
        duration_seconds = data.get('duration_seconds')
        description = data.get('description', data.get('name', ''))

        if not batch_id or not duration_seconds:
            return jsonify({'error': 'Batch ID and duration are required'}), 400

        try:
            batch_id = int(batch_id)
            duration_seconds = int(duration_seconds)
        except ValueError:
            return jsonify({'error': 'Invalid batch ID or duration'}), 400

        # Verify batch exists and user has access
        batch = Batch.query.get(batch_id)
        if not batch:
            return jsonify({'error': 'Batch not found'}), 404

        if current_user.organization_id and batch.organization_id != current_user.organization_id:
            return jsonify({'error': 'Access denied'}), 403

        timer = TimerService.create_timer(batch_id, duration_seconds, description)

        return jsonify({
            'success': True,
            'status': 'success',
            'timer_id': timer.id,
            'message': 'Timer created successfully'
        })

    except Exception as e:
        import traceback
        print(f"Timer creation error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@timers_bp.route('/api/timer-status/<int:timer_id>')
@login_required
def api_timer_status(timer_id):
    """Get current timer status"""
    try:
        status = TimerService.get_timer_status(timer_id)
        if 'error' in status:
            return jsonify(status), 404

        return jsonify(status)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@timers_bp.route('/api/stop-timer/<int:timer_id>', methods=['POST'])
@timers_bp.route('/complete/<int:timer_id>', methods=['POST'])
@login_required
def api_stop_timer(timer_id):
    """Stop/complete an active timer"""
    try:
        success = TimerService.stop_timer(timer_id)
        if success:
            # Get the updated timer for response
            timer_status = TimerService.get_timer_status(timer_id)
            return jsonify({
                'success': True, 
                'message': 'Timer completed',
                'end_time': timer_status.get('end_time')
            })
        else:
            return jsonify({'error': 'Failed to stop timer'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@timers_bp.route('/delete/<int:timer_id>', methods=['POST'])
@login_required
def delete_timer(timer_id):
    """Delete a timer"""
    try:
        from ...models import BatchTimer
        timer = BatchTimer.query.get_or_404(timer_id)

        # Check organization access
        if current_user.organization_id and timer.organization_id != current_user.organization_id:
            return jsonify({'error': 'Access denied'}), 403

        db.session.delete(timer)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Timer deleted'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@timers_bp.route('/api/pause-timer/<int:timer_id>', methods=['POST'])
@login_required
def api_pause_timer(timer_id):
    """Pause an active timer"""
    try:
        success = TimerService.pause_timer(timer_id)
        if success:
            return jsonify({'success': True, 'message': 'Timer paused'})
        else:
            return jsonify({'error': 'Failed to pause timer'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@timers_bp.route('/api/resume-timer/<int:timer_id>', methods=['POST'])
@login_required
def api_resume_timer(timer_id):
    """Resume a paused timer"""
    try:
        success = TimerService.resume_timer(timer_id)
        if success:
            return jsonify({'success': True, 'message': 'Timer resumed'})
        else:
            return jsonify({'error': 'Failed to resume timer'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@timers_bp.route('/api/batch-timers/<int:batch_id>')
@login_required
def api_batch_timers(batch_id):
    """Get all timers for a specific batch"""
    try:
        timers = TimerService.get_batch_timers(batch_id)
        return jsonify({'timers': timers})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@timers_bp.route('/api/expired-timers')
@login_required
def api_expired_timers():
    """Get all expired timers"""
    try:
        expired_timers = TimerService.get_expired_timers()
        return jsonify({'expired_timers': expired_timers})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@timers_bp.route('/api/auto-expire-timers', methods=['POST'])
@login_required
def api_auto_expire_timers():
    """Automatically expire overdue timers"""
    try:
        count = TimerService.auto_expire_timers()
        return jsonify({
            'success': True,
            'expired_count': count,
            'message': f'Marked {count} timers as expired'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@timers_bp.route('/api/timer-summary')
@login_required
def api_timer_summary():
    """Get timer statistics summary"""
    try:
        summary = TimerService.get_timer_summary()
        return jsonify(summary)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@timers_bp.route('/api/cancel/<int:timer_id>', methods=['POST'])
@login_required
def cancel_timer(timer_id):
    """Cancel a timer"""
    try:
        from ...models import BatchTimer
        timer = BatchTimer.query.get_or_404(timer_id)

        # Check organization access
        if current_user.organization_id and timer.organization_id != current_user.organization_id:
            return jsonify({'error': 'Access denied'}), 403

        timer.status = 'cancelled'
        timer.end_time = TimezoneUtils.utc_now()
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Timer "{timer.name}" cancelled'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@timers_bp.route('/api/complete-expired', methods=['POST'])
@login_required
def complete_expired_timers():
    """Manually trigger completion of expired timers"""
    try:
        completed_count = TimerService.complete_expired_timers()

        return jsonify({
            'success': True,
            'message': f'Completed {completed_count} expired timers',
            'completed_count': completed_count
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@timers_bp.route('/api/check-expired')
@login_required
def check_expired_timers():
    """Check for expired timers without completing them"""
    try:
        expired_timers = TimerService.get_expired_timers()

        # Filter by organization for non-developer users
        if current_user.organization_id:
            expired_timers = [t for t in expired_timers if t.organization_id == current_user.organization_id]

        return jsonify({
            'expired_count': len(expired_timers),
            'expired_timers': [{
                'id': timer.id,
                'name': timer.name,
                'batch_id': timer.batch_id,
                'start_time': timer.start_time.isoformat() if timer.start_time else None,
                'duration_seconds': timer.duration_seconds
            } for timer in expired_timers]
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500