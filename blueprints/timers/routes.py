
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from models import db, BatchTimer
from datetime import datetime
from . import timers_bp

@timers_bp.route('/list')
@login_required
def list_timers():
    timers = BatchTimer.query.all()
    timer_data = [{
        'id': t.id,
        'batch_id': t.batch_id,
        'name': t.name,
        'duration_seconds': t.duration_seconds,
        'start_time': t.start_time.isoformat() if t.start_time else None,
        'status': t.status
    } for t in timers]
    return render_template('timer_list.html', timers=timer_data)

@timers_bp.route('/create', methods=['POST'])
@login_required
def create_timer():
    data = request.get_json()
    timer = BatchTimer(
        name=data.get('name'),
        duration_seconds=int(data.get('duration_seconds')),
        start_time=datetime.utcnow(),
        status='active'
    )
    db.session.add(timer)
    db.session.commit()
    return jsonify({'status': 'success', 'timer_id': timer.id})

@timers_bp.route('/complete/<int:timer_id>', methods=['POST'])
@login_required
def complete_timer(timer_id):
    timer = BatchTimer.query.get_or_404(timer_id)
    timer.status = 'completed'
    timer.end_time = datetime.utcnow()
    db.session.commit()
    return jsonify({'status': 'success'})
