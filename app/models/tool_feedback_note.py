"""Persistent support feedback note model.

Synopsis:
Stores normalized support-note submissions for developer triage dashboards.
This table is durable and survives application deploys.
"""

from __future__ import annotations

from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils


class ToolFeedbackNote(db.Model):
    """Durable support-note row grouped by source and flow."""

    __tablename__ = "tool_feedback_note"

    id = db.Column(db.String(32), primary_key=True)
    submitted_at = db.Column(
        db.DateTime, default=TimezoneUtils.utc_now, nullable=False, index=True
    )
    source = db.Column(db.String(180), nullable=False, index=True)
    flow = db.Column(db.String(64), nullable=False, index=True)
    flow_label = db.Column(db.String(80), nullable=False)

    title = db.Column(db.String(160), nullable=True)
    message = db.Column(db.Text, nullable=False)
    context = db.Column(db.String(120), nullable=True)
    page_path = db.Column(db.String(240), nullable=True)
    page_url = db.Column(db.String(512), nullable=True)
    contact_email = db.Column(db.String(254), nullable=True, index=True)

    metadata_json = db.Column(db.JSON, nullable=True)
    request_json = db.Column(db.JSON, nullable=True)
    user_json = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=TimezoneUtils.utc_now,
        onupdate=TimezoneUtils.utc_now,
        nullable=False,
    )

    __table_args__ = (
        db.Index(
            "ix_tool_feedback_note_source_flow_submitted",
            "source",
            "flow",
            "submitted_at",
        ),
    )

    def __repr__(self) -> str:
        return f"<ToolFeedbackNote {self.source}/{self.flow} {self.id}>"
