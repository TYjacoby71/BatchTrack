
from flask import Blueprint, jsonify, request, redirect, url_for, flash, render_template
from flask_login import login_required
from models import db, BatchTimer
from datetime import datetime, timedelta

timers_bp = Blueprint('timers', __name__, url_prefix='/timers')

@timers_bp.route('/', methods=['GET'])
@login_required
def list_timers():
    timers = BatchTimer.query.all()
    return render_template('timer_list.html', timers=timers)

@timers_bp.route('/start/<int:batch_id>', methods=['POST'])
@login_required
def start_timer(batch_id):
    data = request.get_json()
    
    timer = BatchTimer(
        batch_id=batch_id,
        name=data['name'],
        duration_seconds=data['duration_seconds'],
        start_time=datetime.utcnow(),
        status='running'
    )
    
    end_time = timer.start_time + timedelta(seconds=timer.duration_seconds)
    timer.end_time = end_time
    
    db.session.add(timer)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'timer_id': timer.id,
        'name': timer.name,
        'end_time': end_time.isoformat(),
    })

@timers_bp.route('/cancel/<int:timer_id>', methods=['POST'])
@login_required
def cancel_timer(timer_id):
    timer = BatchTimer.query.get_or_404(timer_id)
    timer.status = 'cancelled'
    db.session.commit()
    return jsonify({'status': 'success'})

@timers_bp.route('/complete/<int:timer_id>', methods=['POST'])
@login_required
def complete_timer(timer_id):
    timer = BatchTimer.query.get_or_404(timer_id)
    timer.status = 'completed'
    db.session.commit()
    flash('Timer completed successfully', 'success')
    return redirect(url_for('timers.list_timers'))
