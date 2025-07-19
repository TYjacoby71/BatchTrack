from typing import Dict, List, Optional
from datetime import datetime, timedelta
from flask_login import current_user
from ..models import db, BatchTimer, Batch
from ..utils.timezone_utils import TimezoneUtils
import logging

logger = logging.getLogger(__name__)

class TimerService:
    """Comprehensive timer management service for batch operations"""

    @staticmethod
    def create_timer(batch_id: int, duration_seconds: int, description: str = None) -> BatchTimer:
        """Create a new timer for a batch"""
        try:
            # Get organization from the batch first
            batch = Batch.query.get(batch_id)
            if not batch:
                raise ValueError("Batch not found")

            timer = BatchTimer(
                batch_id=batch_id,
                start_time=TimezoneUtils.utc_now(),
                duration_seconds=duration_seconds,
                status='active',
                name=description or "Timer",
                organization_id=batch.organization_id  # Always use batch's organization
            )

            db.session.add(timer)
            db.session.commit()
            return timer
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def stop_timer(timer_id: int) -> bool:
        """Stop an active timer"""
        timer = BatchTimer.query.get(timer_id)
        if not timer or timer.status != 'active':
            return False

        timer.end_time = TimezoneUtils.utc_now()
        timer.status = 'completed'
        db.session.commit()
        return True

    @staticmethod
    def pause_timer(timer_id: int) -> bool:
        """Pause an active timer"""
        timer = BatchTimer.query.get(timer_id)
        if not timer or timer.status != 'active':
            return False

        timer.status = 'paused'
        db.session.commit()
        return True

    @staticmethod
    def resume_timer(timer_id: int) -> bool:
        """Resume a paused timer"""
        timer = BatchTimer.query.get(timer_id)
        if not timer or timer.status != 'paused':
            return False

        timer.status = 'active'
        db.session.commit()
        return True

    @staticmethod
    def get_timer_status(timer_id: int) -> Dict:
        """Get comprehensive timer status"""
        timer = BatchTimer.query.get(timer_id)
        if not timer:
            return {'error': 'Timer not found'}

        current_time = TimezoneUtils.utc_now()

        # Calculate elapsed time
        if timer.start_time:
            if timer.end_time:
                elapsed_seconds = (timer.end_time - timer.start_time).total_seconds()
            else:
                elapsed_seconds = (current_time - timer.start_time).total_seconds()
        else:
            elapsed_seconds = 0

        # Calculate remaining time
        remaining_seconds = max(0, timer.duration_seconds - elapsed_seconds)

        # Determine if timer is expired
        is_expired = elapsed_seconds > timer.duration_seconds and timer.status == 'active'

        return {
            'id': timer.id,
            'batch_id': timer.batch_id,
            'status': timer.status,
            'start_time': timer.start_time,
            'end_time': timer.end_time,
            'duration_seconds': timer.duration_seconds,
            'elapsed_seconds': int(elapsed_seconds),
            'remaining_seconds': int(remaining_seconds),
            'is_expired': is_expired,
            'description': timer.name
        }

    @staticmethod
    def get_active_timers() -> List[Dict]:
        """Get all active timers for current user's organization"""
        query = BatchTimer.query.filter_by(status='active')

        # Apply organization scoping
        if current_user and current_user.is_authenticated and current_user.organization_id:
            query = query.filter(BatchTimer.organization_id == current_user.organization_id)

        active_timers = query.all()
        return [TimerService.get_timer_status(timer.id) for timer in active_timers]

    @staticmethod
    def get_expired_timers() -> List[Dict]:
        """Get all expired but still active timers"""
        active_timers = TimerService.get_active_timers()
        return [timer for timer in active_timers if timer.get('is_expired', False)]

    @staticmethod
    def get_batch_timers(batch_id: int) -> List[Dict]:
        """Get all timers for a specific batch"""
        query = BatchTimer.query.filter_by(batch_id=batch_id)

        # Apply organization scoping
        if current_user and current_user.is_authenticated and current_user.organization_id:
            query = query.filter(BatchTimer.organization_id == current_user.organization_id)

        timers = query.all()
        return [TimerService.get_timer_status(timer.id) for timer in timers]

    @staticmethod
    def auto_expire_timers() -> int:
        """Automatically mark expired timers as expired and return count"""
        expired_timers = TimerService.get_expired_timers()
        count = 0

        for timer_data in expired_timers:
            timer = BatchTimer.query.get(timer_data['id'])
            if timer and timer.status == 'active':
                timer.status = 'expired'
                timer.end_time = TimezoneUtils.utc_now()
                count += 1

        if count > 0:
            db.session.commit()

        return count

    @staticmethod
    def get_timer_summary() -> Dict:
        """Get summary of timer statistics"""
        query = BatchTimer.query

        # Apply organization scoping
        if current_user and current_user.is_authenticated and current_user.organization_id:
            query = query.filter(BatchTimer.organization_id == current_user.organization_id)

        all_timers = query.all()

        active_count = len([t for t in all_timers if t.status == 'active'])
        expired_timers = TimerService.get_expired_timers()
        expired_count = len(expired_timers)
        completed_count = len([t for t in all_timers if t.status == 'completed'])

        return {
            'total_timers': len(all_timers),
            'active_count': active_count,
            'expired_count': expired_count,
            'completed_count': completed_count,
            'expired_timers': expired_timers
        }

    @staticmethod
    def format_time_display(seconds: int) -> str:
        """Format seconds into human-readable time display"""
        if seconds < 0:
            return "00:00"

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    @staticmethod
    def complete_expired_timers():
        """Automatically complete all expired timers"""
        try:
            current_time = TimezoneUtils.utc_now()

            # Find all active timers that have expired
            expired_timers = BatchTimer.query.filter(
                BatchTimer.status == 'active',
                BatchTimer.start_time.isnot(None),
                BatchTimer.duration_seconds.isnot(None)
            ).all()

            completed_count = 0
            for timer in expired_timers:
                # Calculate when this timer should have ended
                expected_end_time = timer.start_time + timedelta(seconds=timer.duration_seconds)

                if current_time >= expected_end_time:
                    timer.status = 'completed'
                    timer.end_time = expected_end_time  # Use the actual end time, not current time
                    completed_count += 1
                    logger.info(f"Auto-completed expired timer '{timer.name}' for batch {timer.batch_id}")

            if completed_count > 0:
                db.session.commit()
                logger.info(f"Auto-completed {completed_count} expired timers")

            return completed_count

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error completing expired timers: {str(e)}")
            return 0

    @staticmethod
    def get_expired_timers():
        """Get all currently expired but active timers"""
        try:
            current_time = TimezoneUtils.utc_now()

            expired_timers = []
            active_timers = BatchTimer.query.filter(
                BatchTimer.status == 'active',
                BatchTimer.start_time.isnot(None),
                BatchTimer.duration_seconds.isnot(None)
            ).all()

            for timer in active_timers:
                expected_end_time = timer.start_time + timedelta(seconds=timer.duration_seconds)
                if current_time >= expected_end_time:
                    expired_timers.append(timer)

            return expired_timers

        except Exception as e:
            logger.error(f"Error getting expired timers: {str(e)}")
            return []