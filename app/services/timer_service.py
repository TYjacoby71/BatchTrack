import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from flask_login import current_user

from ..models import Batch, BatchTimer, db
from ..utils.timezone_utils import TimezoneUtils
from .event_emitter import EventEmitter

logger = logging.getLogger(__name__)


class TimerService:
    """Comprehensive timer management service for batch operations"""

    @staticmethod
    def _effective_org_id(explicit_org_id: Optional[int] = None) -> Optional[int]:
        """Resolve organization context for the current request."""
        if explicit_org_id is not None:
            return explicit_org_id
        try:
            if current_user and current_user.is_authenticated:
                return getattr(current_user, "organization_id", None)
        except Exception:
            return None
        return None

    @staticmethod
    def _scoped_query(*, organization_id: Optional[int] = None):
        """Return a base timer query scoped to the effective organization."""
        query = BatchTimer.query
        org_id = TimerService._effective_org_id(organization_id)
        if org_id:
            query = query.filter(BatchTimer.organization_id == org_id)
        return query

    @staticmethod
    def _is_timer_expired(timer: BatchTimer, now_utc: datetime) -> bool:
        if not timer.start_time or not timer.duration_seconds:
            return False
        start = TimezoneUtils.ensure_timezone_aware(timer.start_time)
        return now_utc >= start + timedelta(seconds=timer.duration_seconds)

    @staticmethod
    def _serialize_timer(
        timer: BatchTimer, *, now_utc: Optional[datetime] = None
    ) -> Dict:
        if now_utc is None:
            now_utc = TimezoneUtils.utc_now()

        start_time = (
            TimezoneUtils.ensure_timezone_aware(timer.start_time)
            if timer.start_time
            else None
        )
        if timer.end_time:
            end_time = TimezoneUtils.ensure_timezone_aware(timer.end_time)
            elapsed = (end_time - start_time).total_seconds() if start_time else 0
        elif start_time:
            elapsed = (now_utc - start_time).total_seconds()
        else:
            elapsed = 0

        remaining = max(0, (timer.duration_seconds or 0) - elapsed)
        is_expired = False
        if timer.status == "active":
            is_expired = TimerService._is_timer_expired(timer, now_utc)

        return {
            "id": timer.id,
            "batch_id": timer.batch_id,
            "status": timer.status,
            "start_time": timer.start_time,
            "end_time": timer.end_time,
            "duration_seconds": timer.duration_seconds,
            "elapsed_seconds": int(elapsed),
            "remaining_seconds": int(remaining),
            "is_expired": is_expired,
            "description": timer.name,
            "name": timer.name,
            "organization_id": timer.organization_id,
        }

    @staticmethod
    def _bulk_update_expired_timers(
        new_status: str, *, organization_id: Optional[int] = None
    ) -> int:
        now_utc = TimezoneUtils.utc_now()
        query = (
            TimerService._scoped_query(organization_id=organization_id)
            .filter(BatchTimer.status == "active")
            .filter(BatchTimer.start_time.isnot(None))
            .filter(BatchTimer.duration_seconds.isnot(None))
        )

        timers = query.all()
        updated = 0

        for timer in timers:
            if TimerService._is_timer_expired(timer, now_utc):
                timer.status = new_status
                timer.end_time = now_utc
                updated += 1

        if updated:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                raise

        return updated

    @staticmethod
    def create_timer(
        batch_id: int, duration_seconds: int, description: str = None
    ) -> BatchTimer:
        """Create a new timer for a batch"""
        try:
            # Get organization from the batch first
            batch = db.session.get(Batch, batch_id)
            if not batch:
                raise ValueError("Batch not found")

            timer = BatchTimer(
                batch_id=batch_id,
                start_time=TimezoneUtils.utc_now(),
                duration_seconds=duration_seconds,
                status="active",
                name=description or "Timer",
                organization_id=batch.organization_id,  # Always use batch's organization
            )

            db.session.add(timer)
            db.session.commit()
            # Emit timer_started event
            try:
                EventEmitter.emit(
                    event_name="timer_started",
                    properties={
                        "batch_id": batch_id,
                        "duration_seconds": duration_seconds,
                        "description": description,
                    },
                    organization_id=batch.organization_id,
                    user_id=getattr(current_user, "id", None),
                    entity_type="timer",
                    entity_id=timer.id,
                )
            except Exception:
                pass
            return timer
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def stop_timer(timer_id: int) -> bool:
        """Stop an active timer"""
        timer = db.session.get(BatchTimer, timer_id)
        if not timer or timer.status != "active":
            return False

        timer.end_time = TimezoneUtils.utc_now()
        timer.status = "completed"
        db.session.commit()
        # Emit timer_stopped event
        try:
            EventEmitter.emit(
                event_name="timer_stopped",
                properties={
                    "batch_id": timer.batch_id,
                    "duration_seconds": timer.duration_seconds,
                },
                organization_id=timer.batch.organization_id if timer.batch else None,
                user_id=getattr(current_user, "id", None),
                entity_type="timer",
                entity_id=timer.id,
            )
        except Exception:
            pass
        return True

    @staticmethod
    def pause_timer(timer_id: int) -> bool:
        """Pause an active timer"""
        timer = db.session.get(BatchTimer, timer_id)
        if not timer or timer.status != "active":
            return False

        timer.status = "paused"
        db.session.commit()
        return True

    @staticmethod
    def resume_timer(timer_id: int) -> bool:
        """Resume a paused timer"""
        timer = db.session.get(BatchTimer, timer_id)
        if not timer or timer.status != "paused":
            return False

        timer.status = "active"
        db.session.commit()
        return True

    @staticmethod
    def get_timer_status(timer_id: int) -> Dict:
        """Get comprehensive timer status"""
        timer = db.session.get(BatchTimer, timer_id)
        if not timer:
            return {"error": "Timer not found"}
        return TimerService._serialize_timer(timer)

    @staticmethod
    def get_active_timers() -> List[Dict]:
        """Get all active timers for current user's organization"""
        now_utc = TimezoneUtils.utc_now()
        query = TimerService._scoped_query().filter(BatchTimer.status == "active")
        timers = query.all()
        return [
            TimerService._serialize_timer(timer, now_utc=now_utc) for timer in timers
        ]

    @staticmethod
    def get_batch_timers(batch_id: int) -> List[Dict]:
        """Get all timers for a specific batch"""
        now_utc = TimezoneUtils.utc_now()
        query = TimerService._scoped_query().filter(BatchTimer.batch_id == batch_id)
        timers = query.all()
        return [
            TimerService._serialize_timer(timer, now_utc=now_utc) for timer in timers
        ]

    @staticmethod
    def auto_expire_timers() -> int:
        """Automatically mark expired timers as expired and return count"""
        updated = TimerService._bulk_update_expired_timers("expired")
        if updated:
            logger.info("Marked %s timers as expired", updated)
        return updated

    @staticmethod
    def get_timer_summary() -> Dict:
        """Get summary of timer statistics"""
        now_utc = TimezoneUtils.utc_now()
        query = TimerService._scoped_query()
        timers = query.all()

        serialized = [
            TimerService._serialize_timer(timer, now_utc=now_utc) for timer in timers
        ]
        total = len(serialized)
        active = [timer for timer in serialized if timer["status"] == "active"]
        completed_count = sum(
            1 for timer in serialized if timer["status"] == "completed"
        )
        expired_active = [timer for timer in active if timer["is_expired"]]

        return {
            "total_timers": total,
            "active_count": len(active),
            "expired_count": len(expired_active),
            "completed_count": completed_count,
            "expired_timers": expired_active,
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
        """Complete all expired timers"""
        try:
            completed_count = TimerService._bulk_update_expired_timers("completed")
            if completed_count:
                logger.info("Auto-completed %s expired timers", completed_count)
            return {
                "success": True,
                "completed_count": completed_count,
                "message": f"Completed {completed_count} expired timers",
            }
        except Exception as e:
            logger.error(f"Timer completion error: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "completed_count": 0,
                "message": f"Error completing expired timers: {str(e)}",
            }

    @staticmethod
    def get_expired_timers(*, serialize: bool = False):
        """Get all currently expired but active timers.

        Args:
            serialize: When True, return serialized timer dictionaries.
        """
        try:
            now_utc = TimezoneUtils.utc_now()
            query = (
                TimerService._scoped_query()
                .filter(BatchTimer.status == "active")
                .filter(BatchTimer.start_time.isnot(None))
                .filter(BatchTimer.duration_seconds.isnot(None))
            )
            timers = query.all()
            expired = [
                timer
                for timer in timers
                if TimerService._is_timer_expired(timer, now_utc)
            ]
            if serialize:
                return [
                    TimerService._serialize_timer(timer, now_utc=now_utc)
                    for timer in expired
                ]
            return expired
        except Exception as e:
            logger.error(f"Error getting expired timers: {str(e)}", exc_info=True)
            return []
