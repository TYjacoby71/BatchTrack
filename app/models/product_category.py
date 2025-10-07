from ..extensions import db
from .mixins import TimestampMixin


class ProductCategory(TimestampMixin, db.Model):
    __tablename__ = 'product_category'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, unique=True, index=True)
    is_typically_portioned = db.Column(db.Boolean, default=False, nullable=False)
    sku_name_template = db.Column(db.String(256), nullable=True)
    ui_config = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return f"<ProductCategory {self.name} ({'Portioned' if self.is_typically_portioned else 'Bulk'})>"

