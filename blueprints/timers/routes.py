
from flask import render_template, redirect, url_for, flash, request, jsonify
from datetime import datetime, timedelta
from flask_login import login_required
from models import db, BatchTimer, Batch
from datetime import datetime
from . import timers_bp

@timers_bp.route('/list')
@login_required
def list_timers():
    from datetime import timedelta
    timers = BatchTimer.query.all()
    active_batches = Batch.query.filter_by(status='in_progress').all()
    
    timer_data = [{
        'id': t.id,
        'batch_id': t.batch_id,
        'name': t.name,
        'duration_seconds': int(t.duration_seconds),
        'start_time': t.start_time.replace(tzinfo=None).isoformat() if t.start_time else None,
        'end_time': t.end_time.replace(tzinfo=None).isoformat() if t.end_time else None,
        'status': t.status
    } for t in timers]
    
    active_batch_data = [{
        'id': b.id,
        'recipe_name': b.recipe.name if b.recipe else None
    } for b in active_batches]
    
    return render_template('timer_list.html', 
                         timers=timer_data,
                         active_batches=active_batch_data,
                         now=datetime.utcnow())

@timers_bp.route('/create', methods=['POST'])
@login_required
def create_timer():
    data = request.get_json()
    try:
        duration = int(data.get('duration_seconds', 0))
        if duration <= 0:
            return jsonify({'status': 'error', 'message': 'Invalid duration'}), 400
            
        batch_id = data.get('batch_id')
        batch_id = int(batch_id) if batch_id else None
            
        timer = BatchTimer(
            name=data.get('name'),
            duration_seconds=duration,
            batch_id=batch_id,
            start_time=datetime.utcnow(),
            status='active'
        )
        db.session.add(timer)
        db.session.commit()
        return jsonify({'status': 'success', 'timer_id': timer.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'success', 'timer_id': timer.id})

@timers_bp.route('/complete/<int:timer_id>', methods=['POST'])
@login_required
def complete_timer(timer_id):
    timer = BatchTimer.query.get_or_404(timer_id)
    now = datetime.utcnow()
    
    # Check if timer is expired
    if timer.start_time and timer.duration_seconds:
        time_diff = (now - timer.start_time).total_seconds()
        is_expired = time_diff >= timer.duration_seconds
    else:
        is_expired = False
        
    if timer.status == 'active':
        timer.status = 'completed'
        timer.end_time = now
        db.session.commit()
        return jsonify({'status': 'success', 'end_time': now.isoformat()})
    return jsonify({'status': 'error', 'message': 'Timer already completed'})

@timers_bp.route('/delete/<int:timer_id>', methods=['POST'])
@login_required
def delete_timer(timer_id):
    timer = BatchTimer.query.get_or_404(timer_id)
    db.session.delete(timer)
    db.session.commit()
    return jsonify({'status': 'success'})

@timers_bp.route('/status/<int:timer_id>', methods=['POST'])
@login_required
def update_timer_status(timer_id):
    timer = BatchTimer.query.get_or_404(timer_id)
    data = request.get_json()
    now = datetime.utcnow()
    
    if data.get('status') == 'completed':
        timer.status = 'completed'
        timer.end_time = now
        db.session.commit()
        return jsonify({'status': 'success', 'end_time': now.isoformat()})
    elif data.get('status') == 'active':
        timer.status = 'active'
        db.session.commit()
        return jsonify({'status': 'success'})
    
    return jsonify({'status': 'error', 'message': 'Invalid status'})
