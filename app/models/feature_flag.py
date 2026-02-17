from ..extensions import db
from .mixins import TimestampMixin


class FeatureFlag(TimestampMixin, db.Model):
    __tablename__ = "feature_flag"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(128), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)
    enabled = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<FeatureFlag {self.key} enabled={self.enabled}>"
