from ..extensions import db
from .mixins import TimestampMixin
from .db_dialect import is_postgres

_IS_PG = is_postgres()


class ProductCategory(TimestampMixin, db.Model):
    __tablename__ = 'product_category'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, unique=True, index=True)
    is_typically_portioned = db.Column(db.Boolean, default=False, nullable=False)
    sku_name_template = db.Column(db.String(256), nullable=True)
    ui_config = db.Column(db.JSON, nullable=True)
    # Controls whether the recipe form shows category skin UI for this category
    skin_enabled = db.Column(db.Boolean, default=False, nullable=True)

    __table_args__ = tuple([
        # Functional unique index for case-insensitive name lookups (Postgres only due to ::text)
        *([db.Index('ix_product_category_lower_name', db.text('lower(name::text)'), unique=True)] if _IS_PG else []),
    ])

    def __repr__(self):
        return f"<ProductCategory {self.name} ({'Portioned' if self.is_typically_portioned else 'Bulk'})>"

