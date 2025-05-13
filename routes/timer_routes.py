
from flask import Blueprint, redirect, url_for, flash, render_template
from flask_login import login_required
from models import db, BatchTimer

timers_bp = Blueprint('timers', __name__, url_prefix='/timers')

@timers_bp.route('/list')
@login_required
def list_timers():
    timers = BatchTimer.query.all()
    return render_template('timer_list.html', timers=timers)

@timers_bp.route('/batch/<int:batch_id>/save', methods=['POST'])
@login_required
def save_batch_timers(batch_id):
    data = request.get_json()
    timers = data.get('timers', [])
    
    for timer_data in timers:
        timer = BatchTimer.query.get(timer_data['id'])
        if timer and timer.batch_id == batch_id:
            timer.name = timer_data['name']
            timer.duration_seconds = timer_data['duration_seconds']
            timer.completed = timer_data.get('completed', False)
            timer.status = timer_data.get('status', 'pending')
    
    db.session.commit()
    batch_timers = BatchTimer.query.filter_by(batch_id=batch_id).all()
    return jsonify({'timers': [timer.to_dict() for timer in batch_timers]})

@timers_bp.route('/complete/<int:timer_id>', methods=['POST'])
@login_required
def complete_timer(timer_id):
    timer = BatchTimer.query.get_or_404(timer_id)
    timer.completed = True
    db.session.commit()
    flash("Timer marked complete.")
    return redirect(url_for('batches.view_batch_in_progress', batch_identifier=timer.batch_id))
