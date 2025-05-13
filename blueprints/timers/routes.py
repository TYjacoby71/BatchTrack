
from flask import render_template, redirect, url_for, flash
from flask_login import login_required
from models import db, BatchTimer
from . import timers_bp

@timers_bp.route('/list')
@login_required
def list_timers():
    timers = BatchTimer.query.all()
    return render_template('timer_list.html', timers=timers)

@timers_bp.route('/complete/<int:timer_id>', methods=['POST'])
@login_required
def complete_timer(timer_id):
    timer = BatchTimer.query.get_or_404(timer_id)
    timer.completed = True
    db.session.commit()
    flash("Timer marked complete.")
    return redirect(url_for('batches.view_batch_in_progress', batch_identifier=timer.batch_id))
