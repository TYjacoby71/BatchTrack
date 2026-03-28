"""Timer access/read service boundary.

Synopsis:
Provide scoped batch/timer lookup helpers used by timer routes so controller
code avoids direct model queries and persistence calls.

Glossary:
- Module boundary: Defines the ownership scope and responsibilities for this module.
"""

from __future__ import annotations

from app.extensions import db
from app.models import Batch, BatchTimer


class TimerAccessService:
    """Service helpers for timer route access checks and mutations."""

    @staticmethod
    def list_in_progress_batches_for_org(organization_id: int | None) -> list[Batch]:
        query = Batch.scoped().filter_by(status="in_progress")
        if organization_id:
            query = query.filter(Batch.organization_id == organization_id)
        return query.all()

    @staticmethod
    def get_batch(batch_id: int) -> Batch | None:
        return db.session.get(Batch, batch_id)

    @staticmethod
    def get_scoped_timer_or_404(timer_id: int) -> BatchTimer:
        return BatchTimer.scoped().filter_by(id=timer_id).first_or_404()

    @staticmethod
    def delete_timer(timer: BatchTimer) -> None:
        db.session.delete(timer)
        db.session.commit()

    @staticmethod
    def cancel_timer(timer: BatchTimer) -> None:
        from app.utils.timezone_utils import TimezoneUtils

        timer.status = "cancelled"
        timer.end_time = TimezoneUtils.utc_now()
        db.session.commit()
