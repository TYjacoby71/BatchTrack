"""Application settings persistence model.

Synopsis:
Define the SQLAlchemy model used to store key/value application configuration
entries and optional descriptions for administrative management workflows.

Glossary:
- Setting key: Unique identifier used to retrieve a configuration value.
- JSON value: Serialized configuration payload stored for a setting key.
- Timestamp mixin: Shared created/updated metadata columns for model records.
"""

from __future__ import annotations

from ..extensions import db
from .mixins import TimestampMixin


# --- AppSetting model ---
# Purpose: Store key/value runtime configuration records.
# Inputs: Unique setting key plus JSON value/optional description.
# Outputs: Persisted organization-agnostic application setting row.
class AppSetting(TimestampMixin, db.Model):
    __tablename__ = "app_setting"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(128), unique=True, nullable=False, index=True)
    value = db.Column(db.JSON, nullable=True)
    description = db.Column(db.String(255), nullable=True)

    # --- String representation ---
    # Purpose: Provide readable model identity in logs/debug output.
    # Inputs: None.
    # Outputs: "<AppSetting key>" string.
    def __repr__(self) -> str:
        return f"<AppSetting {self.key}>"
